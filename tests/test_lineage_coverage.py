"""Focused tests for the evidence-based lineage coverage calculator.

These are pure-function tests: no database, no FastAPI, no fixtures. The rules
asserted here are the ones Demo 8 shows on screen:

    SQL only                     -> POSSIBLE  / PARTIAL
    SQL + dbt declared           -> POSSIBLE  / PARTIAL (more evidence sources)
    SQL + dbt + runtime complete -> OBSERVED  / COMPLETE
    nothing stored               -> UNKNOWN   / NONE
    run-scoped negative only     -> REFUTED_FOR_RUN / PARTIAL
"""
from __future__ import annotations

from backend.app.services.lineage_coverage import (
    COVERAGE_COMPLETE,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    COVERAGE_RULE_VERSION,
    STATE_OBSERVED,
    STATE_POSSIBLE,
    STATE_REFUTED,
    STATE_UNKNOWN,
    aggregate_edge_evidence,
    evidence_source,
    runtime_coverage_complete,
    state_for_evidence_type,
    strongest_state,
)


def _runtime_row(complete: bool = True, run_id: str = "run_999") -> dict:
    coverage = {
        "coverage_mode": "runtime",
        "parser_status": "PARTIAL",
        "scope": "DATASET",
        "run_covered": True,
        "operator_covered": False,
        "source_dataset_covered": True,
        "target_dataset_covered": True,
        "source_columns_covered": [],
        "target_columns_covered": [],
        "branches_covered": False,
    }
    if not complete:
        coverage["target_dataset_covered"] = False
    return {
        "evidence_type": "RUNTIME_POSITIVE",
        "source_system": "openlineage",
        "run_id": run_id,
        "coverage": coverage,
        "event_time": "2026-11-01T10:00:00+00:00",
    }


def _static_row(edge_type: str = "derived_from", source_system: str = "upload") -> dict:
    return {
        "evidence_type": "STATIC_DEPENDENCY",
        "source_system": source_system,
        "diagnostics": {"edge_type": edge_type, "classification": "DECLARED_METADATA"},
    }


def _declared_row() -> dict:
    return {
        "evidence_type": "STATIC_DEPENDENCY",
        "source_system": "upload",
        "diagnostics": {"edge_type": "declared_dependency"},
    }


def test_no_evidence_is_unknown_and_none():
    result = aggregate_edge_evidence([], "DATASET")

    assert result["state"] == STATE_UNKNOWN
    assert result["coverage"] == COVERAGE_NONE
    assert result["evidence_count"] == 0
    assert result["coverage_basis"] == []
    assert result["coverage_rule_version"] == COVERAGE_RULE_VERSION


def test_static_sql_evidence_is_possible_and_partial():
    result = aggregate_edge_evidence([_static_row()], "DATASET")

    assert result["state"] == STATE_POSSIBLE
    assert result["coverage"] == COVERAGE_PARTIAL
    assert result["coverage_basis"] == ["SQL_STATIC"]
    assert result["evidence_sources"] == ["SQL"]


def test_sql_plus_dbt_is_still_possible_but_has_more_basis():
    sql_only = aggregate_edge_evidence([_static_row()], "DATASET")
    both = aggregate_edge_evidence([_static_row(), _declared_row()], "DATASET")

    assert both["state"] == STATE_POSSIBLE
    assert both["coverage"] == COVERAGE_PARTIAL
    assert set(both["coverage_basis"]) == {"SQL_STATIC", "DBT_DECLARED"}
    assert len(both["coverage_basis"]) > len(sql_only["coverage_basis"])
    assert both["evidence_sources"] == ["DBT_MANIFEST", "SQL"]


def test_runtime_observation_at_dataset_scope_is_observed_and_complete():
    result = aggregate_edge_evidence(
        [_static_row(), _declared_row(), _runtime_row()], "DATASET"
    )

    assert result["state"] == STATE_OBSERVED
    assert result["coverage"] == COVERAGE_COMPLETE
    assert "OPENLINEAGE_RUNTIME" in result["coverage_basis"]
    assert result["run_count"] == 1
    assert result["latest_event_time"] == "2026-11-01T10:00:00+00:00"


def test_runtime_observation_with_incomplete_coverage_is_partial():
    result = aggregate_edge_evidence([_runtime_row(complete=False)], "DATASET")

    assert result["state"] == STATE_OBSERVED
    assert result["coverage"] == COVERAGE_PARTIAL


def test_column_scope_requires_column_and_operator_coverage():
    dataset_scope = {
        "coverage_mode": "runtime",
        "scope": "DATASET",
        "run_covered": True,
        "operator_covered": False,
        "source_dataset_covered": True,
        "target_dataset_covered": True,
        "branches_covered": False,
        "source_columns_covered": [],
        "target_columns_covered": [],
    }
    assert runtime_coverage_complete(dataset_scope, "DATASET") is True

    # The same manifest promoted to a column claim is incomplete: operator,
    # branch and column scope were never observed.
    column_scope = {**dataset_scope, "scope": "COLUMN"}
    assert runtime_coverage_complete(column_scope, "COLUMN") is False

    row = dict(_runtime_row())
    row["coverage"] = {
        **column_scope,
        "operator_covered": True,
        "branches_covered": True,
        "source_columns_covered": ["a"],
        "target_columns_covered": ["b"],
    }
    result = aggregate_edge_evidence([row], "COLUMN")
    assert result["coverage"] == COVERAGE_COMPLETE


def test_structural_coverage_mode_is_never_complete():
    row = _runtime_row()
    row["coverage"] = {**row["coverage"], "coverage_mode": "structural"}

    assert runtime_coverage_complete(row["coverage"], "DATASET") is False
    assert aggregate_edge_evidence([row], "DATASET")["coverage"] == COVERAGE_PARTIAL


def test_run_scoped_negative_evaluation_is_refuted_without_positive_evidence():
    row = {"evidence_type": "RUNTIME_NEGATIVE_EVALUATION", "run_id": "run_1", "coverage": {}}
    result = aggregate_edge_evidence([row], "DATASET")

    assert result["state"] == STATE_REFUTED
    assert "run-scoped" in result["state_reason"]


def test_positive_runtime_evidence_wins_over_a_negative_evaluation():
    result = aggregate_edge_evidence(
        [
            {"evidence_type": "RUNTIME_NEGATIVE_EVALUATION", "run_id": "run_1"},
            _runtime_row(run_id="run_2"),
        ],
        "DATASET",
    )

    assert result["state"] == STATE_OBSERVED


def test_coverage_payload_may_arrive_as_json_text():
    import json

    row = _runtime_row()
    row["coverage"] = json.dumps(row["coverage"])

    assert aggregate_edge_evidence([row], "DATASET")["coverage"] == COVERAGE_COMPLETE


def test_evidence_source_mapping():
    assert evidence_source("RUNTIME_POSITIVE", "openlineage") == "OPENLINEAGE"
    assert evidence_source("DBT_DECLARED", "dbt_manifest") == "DBT_MANIFEST"
    assert evidence_source("STATIC_DEPENDENCY", "upload", {"edge_type": "declared_dependency"}) == "DBT_MANIFEST"
    assert evidence_source("STATIC_DEPENDENCY", "sql", {"edge_type": "derived_from"}) == "SQL"
    assert evidence_source("STATIC_DEPENDENCY", "upload", None) == "SQL"
    assert evidence_source(None, None, None) == "OTHER"


def test_strongest_state_prefers_observed_then_refuted_then_possible():
    assert strongest_state(["UNKNOWN", "POSSIBLE"]) == STATE_POSSIBLE
    assert strongest_state(["POSSIBLE", "REFUTED_FOR_RUN"]) == STATE_REFUTED
    assert strongest_state(["REFUTED_FOR_RUN", "OBSERVED"]) == STATE_OBSERVED
    assert strongest_state([]) == STATE_UNKNOWN


def test_state_for_evidence_type_is_the_single_row_rule():
    """The catalog read model and the edge aggregate share this mapping."""
    assert state_for_evidence_type("RUNTIME_POSITIVE") == STATE_OBSERVED
    assert state_for_evidence_type("runtime_positive") == STATE_OBSERVED
    assert state_for_evidence_type("RUNTIME_NEGATIVE_EVALUATION") == STATE_REFUTED
    assert state_for_evidence_type("STATIC_DEPENDENCY") == STATE_POSSIBLE
    assert state_for_evidence_type("DBT_DECLARED") == STATE_POSSIBLE
    assert state_for_evidence_type("SOMETHING_ELSE") == STATE_UNKNOWN
    assert state_for_evidence_type(None) == STATE_UNKNOWN


def test_aggregate_uses_the_row_rule_for_its_precedence():
    assert aggregate_edge_evidence(
        [{"evidence_type": "STATIC_DEPENDENCY"}], "DATASET"
    )["state"] == state_for_evidence_type("STATIC_DEPENDENCY")
    assert aggregate_edge_evidence(
        [{"evidence_type": "STATIC_DEPENDENCY"}, {"evidence_type": "RUNTIME_POSITIVE"}],
        "DATASET",
    )["state"] == state_for_evidence_type("RUNTIME_POSITIVE")
