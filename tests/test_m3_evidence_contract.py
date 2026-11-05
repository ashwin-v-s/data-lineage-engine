"""M3 checks for evidence strength and conservative coverage handling."""
from __future__ import annotations

from backend.app.api.routes.dependency import _coverage_from_payload
from backend.app.services.evidence_strength import evidence_strength


def _complete_coverage():
    return {
        "run_covered": True,
        "operator_covered": True,
        "source_dataset_covered": True,
        "target_dataset_covered": True,
        "source_columns_covered": ["source-column"],
        "target_columns_covered": ["target-column"],
        "branches_covered": True,
        "coverage_mode": "runtime",
        "parser_status": "SUPPORTED",
    }


def test_missing_runtime_coverage_is_not_filled_with_true_defaults():
    assert _coverage_from_payload(None) is None
    assert _coverage_from_payload({}) is None


def test_partial_runtime_coverage_preserves_false_fields():
    raw = _complete_coverage()
    raw["branches_covered"] = False
    result = _coverage_from_payload(raw)
    assert result is not None
    assert result.branches_covered is False


def test_invalid_coverage_mode_is_unknown_to_the_adapter():
    raw = _complete_coverage()
    raw["coverage_mode"] = "made_up"
    assert _coverage_from_payload(raw) is None


def test_strength_is_high_only_for_observed_runtime_with_complete_coverage():
    assert evidence_strength(
        state="OBSERVED", evidence_type="RUNTIME_POSITIVE",
        coverage=_complete_coverage(), parser_status="SUPPORTED",
    ) == "High"
    incomplete = _complete_coverage()
    incomplete["branches_covered"] = False
    assert evidence_strength(
        state="OBSERVED", evidence_type="RUNTIME_POSITIVE",
        coverage=incomplete, parser_status="SUPPORTED",
    ) == "Low"


def test_supported_declarations_are_medium_and_unknowns_low():
    assert evidence_strength(
        state="POSSIBLE", evidence_type="STATIC_DEPENDENCY",
        coverage=None, parser_status="SUPPORTED",
    ) == "Medium"
    assert evidence_strength(
        state="UNKNOWN", evidence_type="RUNTIME_POSITIVE",
        coverage=None, parser_status=None,
    ) == "Low"


def test_strength_rule_never_returns_a_numeric_score():
    assert evidence_strength(
        state="OBSERVED", evidence_type="RUNTIME_POSITIVE",
        coverage=_complete_coverage(), parser_status="SUPPORTED",
    ) in {"High", "Medium", "Low"}
