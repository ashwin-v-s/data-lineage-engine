"""
Tests for OpenLineageRuntimeEvidenceAdapter.

Verifies the adapter satisfies contracts.interfaces.RuntimeEvidenceProvider
and correctly maps local OpenLineage RuntimeEvidence to contracts RuntimeEvidence.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from contracts.evidence import RuntimeEvidence as ContractsRE
from contracts.interfaces import RawEvent, RuntimeExtraction
from contracts.types import EvidenceType, Granularity
from ingestion.openlineage.runtime_evidence_adapter import (
    OpenLineageRuntimeEvidenceAdapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_event(
    run_id: str = "run-001",
    event_type: str = "COMPLETE",
    inputs: list | None = None,
    outputs: list | None = None,
) -> RawEvent:
    payload = {
        "eventType": event_type,
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {"runId": run_id},
        "job": {"namespace": "kairos://test", "name": "test_job"},
        "inputs":  inputs  or [{"namespace": "pg://db", "name": "employees"}],
        "outputs": outputs or [{"namespace": "pg://db", "name": "out_adjusted"}],
        "producer": "kairos-test",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    phash = hashlib.sha256(canonical.encode()).hexdigest()
    return RawEvent(event_id=phash, payload=payload, payload_hash=phash)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestAdapterProtocolConformance:
    """The adapter must satisfy the RuntimeEvidenceProvider Protocol signature."""

    def test_normalize_returns_runtime_extraction(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        raw = _make_raw_event()
        result = adapter.normalize("run-001", [raw])
        assert isinstance(result, RuntimeExtraction)

    def test_extraction_evidence_is_tuple(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert isinstance(result.evidence, tuple)

    def test_extraction_diagnostics_is_tuple(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert isinstance(result.diagnostics, tuple)

    def test_evidence_items_are_contracts_runtime_evidence(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        for ev in result.evidence:
            assert isinstance(ev, ContractsRE)


# ---------------------------------------------------------------------------
# COMPLETE events produce RUNTIME_POSITIVE evidence
# ---------------------------------------------------------------------------

class TestCompleteEventProducesEvidence:
    def test_complete_event_produces_one_evidence_row(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert len(result.evidence) == 1

    def test_evidence_type_is_runtime_positive(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].evidence_type == EvidenceType.RUNTIME_POSITIVE

    def test_evidence_granularity_is_dataset(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].key.granularity == Granularity.DATASET

    def test_evidence_source_system_is_openlineage(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].source_system == "openlineage"

    def test_evidence_run_id_matches(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-abc", [_make_raw_event(run_id="run-abc")])
        assert result.evidence[0].key.run_id == "run-abc"

    def test_evidence_is_not_mock(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].is_mock is False

    def test_evidence_id_is_deterministic(self):
        adapter1 = OpenLineageRuntimeEvidenceAdapter()
        adapter2 = OpenLineageRuntimeEvidenceAdapter()
        raw = _make_raw_event()
        r1 = adapter1.normalize("run-001", [raw])
        r2 = adapter2.normalize("run-001", [raw])
        assert r1.evidence[0].evidence_id == r2.evidence[0].evidence_id


# ---------------------------------------------------------------------------
# Non-COMPLETE events produce no evidence
# ---------------------------------------------------------------------------

class TestNonCompleteEventsProduceNoEvidence:
    @pytest.mark.parametrize("event_type", ["START", "FAIL", "ABORT", "RUNNING", "OTHER"])
    def test_non_complete_produces_empty_evidence(self, event_type: str):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        raw = _make_raw_event(event_type=event_type)
        result = adapter.normalize("run-001", [raw])
        assert len(result.evidence) == 0

    def test_empty_input_produces_empty_evidence(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [])
        assert result.evidence == ()
        assert result.diagnostics == ()


# ---------------------------------------------------------------------------
# Missing events must NEVER produce negative evidence
# ---------------------------------------------------------------------------

class TestMissingEventsNeverNegative:
    def test_empty_batch_produces_no_evidence(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [])
        assert result.evidence == ()

    def test_no_runtime_negative_evaluation_in_output(self):
        """No path through the adapter should yield RUNTIME_NEGATIVE_EVALUATION."""
        adapter = OpenLineageRuntimeEvidenceAdapter()
        events = [_make_raw_event(event_type=et) for et in ["START", "COMPLETE", "FAIL"]]
        result = adapter.normalize("run-001", events)
        for ev in result.evidence:
            assert ev.evidence_type != EvidenceType.RUNTIME_NEGATIVE_EVALUATION, (
                "Adapter produced a RUNTIME_NEGATIVE_EVALUATION — "
                "absence of events must never create negative evidence."
            )


# ---------------------------------------------------------------------------
# Duplicate events are silently dropped
# ---------------------------------------------------------------------------

class TestDuplicateHandling:
    def test_duplicate_event_is_dropped(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        raw = _make_raw_event()
        result = adapter.normalize("run-001", [raw, raw])
        # First event accepted, second is a duplicate
        assert len(result.evidence) == 1

    def test_duplicate_noted_in_diagnostics(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        raw = _make_raw_event()
        result = adapter.normalize("run-001", [raw, raw])
        assert any("duplicate_event_dropped" in d for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Run ID mismatch — events for a different run are not included
# ---------------------------------------------------------------------------

class TestRunIdFiltering:
    def test_event_for_different_run_id_is_excluded(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        raw_wrong = _make_raw_event(run_id="run-other")
        result = adapter.normalize("run-target", [raw_wrong])
        assert len(result.evidence) == 0
        assert any("mismatch" in d for d in result.diagnostics)

    def test_only_matching_run_events_included(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        raw_match = _make_raw_event(run_id="run-target")
        # Create a distinct event for the wrong run
        wrong_payload = {
            "eventType": "COMPLETE",
            "eventTime": "2026-10-01T08:01:00Z",
            "run": {"runId": "run-other"},
            "job": {"name": "other_job"},
            "inputs": [{"namespace": "pg://db", "name": "other_table"}],
            "outputs": [{"namespace": "pg://db", "name": "other_out"}],
        }
        canonical = json.dumps(wrong_payload, sort_keys=True, separators=(",", ":"))
        phash = hashlib.sha256(canonical.encode()).hexdigest()
        raw_wrong = RawEvent(event_id=phash, payload=wrong_payload, payload_hash=phash)

        result = adapter.normalize("run-target", [raw_match, raw_wrong])
        assert len(result.evidence) == 1
        assert result.evidence[0].key.run_id == "run-target"


# ---------------------------------------------------------------------------
# Coverage vector correctness
# ---------------------------------------------------------------------------

class TestCoverageVector:
    def test_coverage_mode_is_runtime(self):
        from contracts.types import CoverageMode
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].coverage.coverage_mode == CoverageMode.RUNTIME

    def test_run_covered_is_true(self):
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].coverage.run_covered is True

    def test_branches_covered_is_false(self):
        """
        Dataset-boundary events cannot assert branch coverage.
        is_complete_for() must return False for any column-level key.
        """
        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        assert result.evidence[0].coverage.branches_covered is False

    def test_coverage_is_not_complete_for_column_level_key(self):
        """
        A dataset-boundary event must never satisfy is_complete_for() on a
        column-level DependencyKey — which would allow REFUTED_FOR_RUN.
        """
        from contracts.types import DependencyKey, Granularity, TemporalContext

        adapter = OpenLineageRuntimeEvidenceAdapter()
        result = adapter.normalize("run-001", [_make_raw_event()])
        ev = result.evidence[0]
        col_key = DependencyKey(
            run_id="run-001",
            source_column_id="employees.salary",
            target_column_id="out_adjusted.adjusted_salary",
            granularity=Granularity.COLUMN,
            temporal_context=TemporalContext(),
        )
        assert ev.coverage.is_complete_for(col_key) is False, (
            "Dataset-boundary coverage must not satisfy is_complete_for() "
            "at column granularity — that would allow false REFUTED_FOR_RUN."
        )
