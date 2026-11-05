"""
RuntimeEvidenceAdapter
──────────────────────
Adapts the OpenLineage RuntimeEvidenceNormalizer to satisfy the
contracts.interfaces.RuntimeEvidenceProvider Protocol.

The contracts Protocol expects:
    normalize(run_id: str, raw_events: Sequence[RawEvent]) -> RuntimeExtraction

The existing normalizer works on raw dicts and returns a local RuntimeEvidence
type (ingestion/openlineage/models.py).  This adapter:
  1. Unpacks each RawEvent.payload dict.
  2. Calls RuntimeEvidenceNormalizer.normalize() on each one.
  3. Maps the local RuntimeEvidence → contracts.evidence.RuntimeEvidence.
  4. Returns a RuntimeExtraction containing only RUNTIME_POSITIVE evidence.

Invariants preserved:
  - A missing event (None from normalizer) is never converted to negative
    evidence.
  - Duplicate events (same payload_hash) are silently dropped.
  - The normalizer's deduplication state is fresh per adapter instance.
  - RUNTIME_NEGATIVE_EVALUATION is never produced here; the contracts
    RuntimeEvidence.__post_init__ would reject it without complete coverage.
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence, Tuple

from contracts.evidence import RuntimeEvidence as ContractsRuntimeEvidence
from contracts.interfaces import RawEvent, RuntimeExtraction
from contracts.types import (
    CoverageMode,
    CoverageVector,
    DependencyKey,
    EvidenceType,
    Granularity,
    ParserStatus,
    TemporalContext,
)

from .normalizer import RuntimeEvidenceNormalizer
from .models import RuntimeEvidence as LocalRuntimeEvidence


def _dataset_level_coverage(run_id: str, source: str, target: str) -> CoverageVector:
    """
    Build a dataset-boundary CoverageVector for a COMPLETE OpenLineage event.

    What we can assert at dataset level:
    - run_covered = True  (we have a COMPLETE event for this run)
    - source_dataset_covered = True
    - target_dataset_covered = True
    - Everything else = False / empty  (no column or branch information)

    This coverage vector correctly fails is_complete_for() for any column-level
    DependencyKey — which is correct, because we cannot issue a negative
    evaluation from a dataset-boundary event.
    """
    return CoverageVector(
        run_covered=True,
        operator_covered=False,
        source_dataset_covered=True,
        target_dataset_covered=True,
        source_columns_covered=(source,),
        target_columns_covered=(target,),
        branches_covered=False,
        coverage_mode=CoverageMode.RUNTIME,
        parser_status=ParserStatus.UNSUPPORTED,
    )


def _evidence_id(run_id: str, source: str, target: str, payload_hash: str) -> str:
    """Deterministic evidence_id — same run+pair always yields the same id."""
    raw = json.dumps(
        {"run_id": run_id, "source": source, "target": target, "hash": payload_hash},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "ol-adapter:" + hashlib.sha256(raw.encode()).hexdigest()


def _local_to_contracts(
    local: LocalRuntimeEvidence,
    run_id: str,
) -> list[ContractsRuntimeEvidence]:
    """
    Convert one local RuntimeEvidence (flat datasets list) into zero or more
    contracts RuntimeEvidence objects (one per input×output pair in the event).

    Only COMPLETE events produce records — the normalizer already filters to
    COMPLETE, but we double-check event_type here for defence in depth.

    The local model stores inputs/outputs as a list of "namespace:name" strings.
    We produce one RUNTIME_POSITIVE evidence record per (input, output) pair.
    This is an observation of a dataset boundary — NOT a cartesian-product
    lineage claim.
    """
    if local.event_type.upper() != "COMPLETE":
        return []

    records: list[ContractsRuntimeEvidence] = []

    for source in local.inputs:
        for target in local.outputs:
            key = DependencyKey(
                run_id=run_id,
                source_column_id=source,
                target_column_id=target,
                granularity=Granularity.DATASET,
                temporal_context=TemporalContext(),
            )
            coverage = _dataset_level_coverage(run_id, source, target)
            eid = _evidence_id(run_id, source, target, local.payload_hash)

            records.append(
                ContractsRuntimeEvidence(
                    evidence_id=eid,
                    evidence_type=EvidenceType.RUNTIME_POSITIVE,
                    key=key,
                    source_system="openlineage",
                    event_time=local.event_time,
                    coverage=coverage,
                    raw_payload_hash=local.payload_hash,
                    is_mock=False,
                )
            )

    return records


class OpenLineageRuntimeEvidenceAdapter:
    """
    Satisfies contracts.interfaces.RuntimeEvidenceProvider.

    Usage:
        adapter = OpenLineageRuntimeEvidenceAdapter()
        extraction = adapter.normalize(run_id, raw_events)
        # extraction.evidence is a tuple of contracts RuntimeEvidence objects
        # extraction.diagnostics carries any normalizer warnings
    """

    def normalize(
        self,
        run_id: str,
        raw_events: Sequence[RawEvent],
    ) -> RuntimeExtraction:
        """
        Normalize a sequence of raw events for a given run_id.

        Each RawEvent.payload is passed through RuntimeEvidenceNormalizer.
        Only COMPLETE events produce evidence records.
        Duplicates within the batch are silently dropped (normalizer tracks
        seen event_ids and payload_hashes per call).
        An empty input or a run with only non-COMPLETE events produces an
        empty evidence tuple — never a negative record.
        """
        normalizer = RuntimeEvidenceNormalizer()
        all_records: list[ContractsRuntimeEvidence] = []
        diagnostics: list[str] = []

        for raw_event in raw_events:
            local = normalizer.normalize(raw_event.payload)

            if local is None:
                # Duplicate — silently dropped. Not a negative.
                diagnostics.append(
                    f"duplicate_event_dropped:{raw_event.event_id}"
                )
                continue

            # Only process events that match the requested run_id.
            if local.run_id and local.run_id != run_id:
                diagnostics.append(
                    f"event_run_id_mismatch:expected={run_id},got={local.run_id}"
                )
                continue

            if local.diagnostics:
                diagnostics.extend(local.diagnostics)

            records = _local_to_contracts(local, run_id)
            all_records.extend(records)

        return RuntimeExtraction(
            evidence=tuple(all_records),
            diagnostics=tuple(diagnostics),
        )
