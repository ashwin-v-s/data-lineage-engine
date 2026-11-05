"""
ReferenceInterpreterProvider
─────────────────────────────
Independent ground-truth provider for the restricted benchmark SQL subset.

Implements BOTH interfaces:
  - research.ground_truth.provider.GroundTruthProvider (ABC)
      determine(source_column, target_column) -> research GroundTruthResult
      Used by standalone research scripts and tests.

  - contracts.interfaces.GroundTruthProvider (Protocol)
      supports(case) -> SupportReport
      compute(case, run_id) -> contracts GroundTruthResult
      Used by the experiment runner (research/experiments/run.py).

Independence rule: this module must not bring in sqlglot, ingestion,
research.reasoning, or research.baselines — checked by CI.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Tuple

from contracts.truth import GroundTruthRecord, TruthLabel
from contracts.types import DependencyKey, Granularity, TemporalContext

from .provider import (
    GroundTruthProvider,
    GroundTruthResult,
    PropagationLabel,
)

if TYPE_CHECKING:
    # Imported only for type checking — never at runtime from the reasoning path.
    from contracts.interfaces import BenchmarkCase, GroundTruthResult as ContractsGTResult, SupportReport


class ReferenceInterpreterProvider(GroundTruthProvider):
    """
    Ground-truth provider backed by a hand-verified propagation map.

    The propagation map is a dict[tuple[source_column, target_column], bool].
    True  → the source column propagated to the target in this case.
    False → it did not.

    For the benchmark corpus (W03–W09) these maps are derived from
    ingestion/sql/corpus/W*.json "expected" sections, verified by M1 (static
    analysis owner) and M2 (ground-truth owner).

    This provider never imports SQLGlot, ingestion, or the reasoning engine.
    """

    name = "reference_interpreter"
    version = "reference-1.0"

    def __init__(
        self,
        propagation_map: dict[tuple[str, str], bool],
        version: str = "reference-1.0",
    ) -> None:
        self.propagation_map = propagation_map
        self.version = version

    # ------------------------------------------------------------------
    # research.ground_truth.provider.GroundTruthProvider (ABC interface)
    # ------------------------------------------------------------------

    def determine(
        self,
        source_column: str,
        target_column: str,
    ) -> GroundTruthResult:
        """
        Return PROPAGATED or NOT_PROPAGATED for a single (source, target) pair.

        A pair not in the propagation map defaults to NOT_PROPAGATED — absence
        from the expected set means the dependency does not exist for this case.
        """
        key = (source_column, target_column)
        propagated = self.propagation_map.get(key, False)
        label = PropagationLabel.PROPAGATED if propagated else PropagationLabel.NOT_PROPAGATED

        artifact = {
            "source_column": source_column,
            "target_column": target_column,
            "label": label.value,
            "provider": "reference_interpreter",
            "version": self.version,
        }
        canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
        artifact_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return GroundTruthResult(
            source_column=source_column,
            target_column=target_column,
            label=label,
            provider="reference_interpreter",
            version=self.version,
            artifact_hash=artifact_hash,
        )

    # ------------------------------------------------------------------
    # contracts.interfaces.GroundTruthProvider (Protocol interface)
    # Used by research/experiments/run.py
    # ------------------------------------------------------------------

    def supports(self, case: "BenchmarkCase") -> "SupportReport":
        """
        All cases are supported by the reference interpreter as long as a
        propagation map was supplied at construction time.
        """
        from contracts.interfaces import SupportReport  # local import — avoids top-level circular risk

        if not self.propagation_map:
            return SupportReport(
                supported=False,
                reasons=("Empty propagation map — no pairs to evaluate.",),
            )
        return SupportReport(supported=True, reasons=("Hand-verified propagation map available.",))

    def compute(
        self,
        case: "BenchmarkCase",
        run_id: str,
    ) -> "ContractsGTResult":
        """
        Produce a contracts-shaped GroundTruthResult for the experiment runner.

        Each (source_column, target_column) pair in the propagation map becomes
        one GroundTruthRecord keyed by (run_id, source_column, target_column).
        Pairs absent from the map are NOT included (they are NOT_PROPAGATED by
        absence, which the experiment runner treats as the closed-world default).
        """
        from contracts.interfaces import GroundTruthResult as ContractsGTResult  # local import

        records: list[GroundTruthRecord] = []
        artifact_inputs: list[dict] = []

        for (source_col, target_col), propagated in self.propagation_map.items():
            label = TruthLabel.PROPAGATED if propagated else TruthLabel.NOT_PROPAGATED
            dep_key = DependencyKey(
                run_id=run_id,
                source_column_id=source_col,
                target_column_id=target_col,
                granularity=Granularity.COLUMN,
                temporal_context=TemporalContext(),
            )
            records.append(
                GroundTruthRecord(
                    key=dep_key,
                    label=label,
                    mechanism="reference_interpreter",
                    provider_version=self.version,
                    provenance_ref=f"case:{case.case_id}:run:{run_id}",
                    is_mock=False,
                )
            )
            artifact_inputs.append(
                {
                    "source_column": source_col,
                    "target_column": target_col,
                    "label": label.value,
                    "run_id": run_id,
                    "case_id": case.case_id,
                }
            )

        # Deterministic hash over the full set of records for this case+run.
        canonical = json.dumps(
            {"provider": "reference_interpreter", "version": self.version, "records": artifact_inputs},
            sort_keys=True,
            separators=(",", ":"),
        )
        artifact_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return ContractsGTResult(
            records=tuple(records),
            status="SUPPORTED",
            unsupported_reasons=(),
            artifact_hash=artifact_hash,
        )
