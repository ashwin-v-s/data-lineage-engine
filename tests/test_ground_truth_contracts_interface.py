"""
Tests for ReferenceInterpreterProvider and ProvSQLProvider satisfying
the contracts.interfaces.GroundTruthProvider Protocol (supports + compute).

These tests verify the bridge between the research ABC (determine) and the
experiment-runner Protocol (supports/compute).  They do NOT import the
reasoning engine or baselines — ground truth remains independent.
"""
from __future__ import annotations

import pytest

from contracts.interfaces import BenchmarkCase
from contracts.truth import TruthLabel
from contracts.types import Granularity
from research.ground_truth.provider import PropagationLabel
from research.ground_truth.reference_interpreter import ReferenceInterpreterProvider
from research.ground_truth.provsql_provider import ProvSQLProvider


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CASE = BenchmarkCase(
    case_id="W03_case_when",
    sql="SELECT CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary FROM employees",
    input_dataset_ref="employees",
    split="development",
)

PROP_MAP = {
    ("employees.country", "adjusted_salary"): True,
    ("employees.salary",  "adjusted_salary"): True,
    ("employees.name",    "adjusted_salary"): False,
}


# ---------------------------------------------------------------------------
# ReferenceInterpreterProvider: supports() / compute()
# ---------------------------------------------------------------------------

class TestReferenceInterpreterContractsInterface:
    def test_supports_returns_true_with_populated_map(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        report = provider.supports(CASE)
        assert report.supported is True

    def test_supports_returns_false_with_empty_map(self):
        provider = ReferenceInterpreterProvider({})
        report = provider.supports(CASE)
        assert report.supported is False

    def test_compute_returns_contracts_ground_truth_result(self):
        from contracts.interfaces import GroundTruthResult as ContractsGTResult
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.compute(CASE, run_id="run-001")
        assert isinstance(result, ContractsGTResult)
        assert result.status == "SUPPORTED"
        assert result.artifact_hash != ""
        assert len(result.unsupported_reasons) == 0

    def test_compute_includes_all_map_pairs_as_records(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.compute(CASE, run_id="run-001")
        # All 3 pairs in the map should be present
        assert len(result.records) == 3

    def test_compute_propagated_pairs_have_correct_labels(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.compute(CASE, run_id="run-001")
        labels = {
            (r.key.source_column_id, r.key.target_column_id): r.label
            for r in result.records
        }
        assert labels[("employees.country", "adjusted_salary")] == TruthLabel.PROPAGATED
        assert labels[("employees.salary",  "adjusted_salary")] == TruthLabel.PROPAGATED
        assert labels[("employees.name",    "adjusted_salary")] == TruthLabel.NOT_PROPAGATED

    def test_compute_records_use_supplied_run_id(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.compute(CASE, run_id="run-xyz")
        for record in result.records:
            assert record.key.run_id == "run-xyz"

    def test_compute_records_use_column_granularity(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.compute(CASE, run_id="run-001")
        for record in result.records:
            assert record.key.granularity == Granularity.COLUMN

    def test_compute_records_mechanism_is_reference_interpreter(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.compute(CASE, run_id="run-001")
        for record in result.records:
            assert record.mechanism == "reference_interpreter"
            assert record.is_mock is False

    def test_compute_artifact_hash_is_deterministic(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        first  = provider.compute(CASE, run_id="run-001")
        second = provider.compute(CASE, run_id="run-001")
        assert first.artifact_hash == second.artifact_hash

    def test_compute_different_run_ids_produce_different_hashes(self):
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result_a = provider.compute(CASE, run_id="run-001")
        result_b = provider.compute(CASE, run_id="run-002")
        assert result_a.artifact_hash != result_b.artifact_hash

    def test_determine_still_works_after_compute(self):
        """The research ABC determine() must remain callable independently."""
        provider = ReferenceInterpreterProvider(PROP_MAP)
        result = provider.determine("employees.salary", "adjusted_salary")
        assert result.label == PropagationLabel.PROPAGATED
        assert result.provider == "reference_interpreter"


# ---------------------------------------------------------------------------
# ProvSQLProvider: supports() / compute()
# ---------------------------------------------------------------------------

PROVSQL_ARTIFACT = {
    "case_id": "W03_case_when",
    "propagated_pairs": [
        ["employees.country", "adjusted_salary"],
        ["employees.salary",  "adjusted_salary"],
    ],
    "provsql_version": "1.4.0",
    "query_hash": "abc123",
}


class TestProvSQLContractsInterface:
    def test_supports_returns_true_with_valid_artifact(self):
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        report = provider.supports(CASE)
        assert report.supported is True

    def test_supports_returns_false_with_missing_pairs(self):
        provider = ProvSQLProvider({"provsql_version": "1.4.0"})
        report = provider.supports(CASE)
        assert report.supported is False

    def test_compute_returns_contracts_ground_truth_result(self):
        from contracts.interfaces import GroundTruthResult as ContractsGTResult
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        result = provider.compute(CASE, run_id="run-001")
        assert isinstance(result, ContractsGTResult)
        assert result.status == "SUPPORTED"

    def test_compute_only_includes_propagated_pairs(self):
        """ProvSQL closed-world: only pairs in propagated_pairs are PROPAGATED."""
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        result = provider.compute(CASE, run_id="run-001")
        assert len(result.records) == 2
        for record in result.records:
            assert record.label == TruthLabel.PROPAGATED

    def test_compute_records_use_supplied_run_id(self):
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        result = provider.compute(CASE, run_id="run-provsql")
        for record in result.records:
            assert record.key.run_id == "run-provsql"

    def test_compute_records_mechanism_is_provsql(self):
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        result = provider.compute(CASE, run_id="run-001")
        for record in result.records:
            assert record.mechanism == "provsql"
            assert record.is_mock is False

    def test_compute_artifact_hash_is_deterministic(self):
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        first  = provider.compute(CASE, run_id="run-001")
        second = provider.compute(CASE, run_id="run-001")
        assert first.artifact_hash == second.artifact_hash

    def test_determine_still_works(self):
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        result = provider.determine("employees.country", "adjusted_salary")
        assert result.label == PropagationLabel.PROPAGATED

    def test_determine_not_propagated_for_absent_pair(self):
        provider = ProvSQLProvider(PROVSQL_ARTIFACT)
        result = provider.determine("employees.name", "adjusted_salary")
        assert result.label == PropagationLabel.NOT_PROPAGATED
