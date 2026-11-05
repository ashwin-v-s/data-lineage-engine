"""Rule-based ordinal evidence strength. This is not a probability or score."""
from __future__ import annotations

from typing import Any


STRENGTH_RULE_VERSION = "kairos.evidence-strength.v1"


def evidence_strength(
    *,
    state: str | None,
    evidence_type: str | None,
    coverage: Any,
    parser_status: str | None,
) -> str:
    """Return High/Medium/Low using the published Architecture v2 C1 mapping.

    High requires observed runtime evidence with explicit complete runtime
    coverage and a supported parser. Static or declared evidence is Medium
    only when parsing is supported. Unknown, partial, or unscoped evidence is
    Low. No numeric value is stored or returned.
    """
    kind = (evidence_type or "").upper()
    status = (parser_status or "").upper()
    if isinstance(coverage, str):
        try:
            import json
            coverage = json.loads(coverage)
        except (TypeError, ValueError):
            coverage = None
    complete = isinstance(coverage, dict) and (
        coverage.get("coverage_mode") == "runtime"
        and coverage.get("parser_status", "SUPPORTED") == "SUPPORTED"
        and all(coverage.get(key) is True for key in (
            "run_covered", "operator_covered", "source_dataset_covered",
            "target_dataset_covered", "branches_covered",
        ))
        and bool(coverage.get("source_columns_covered"))
        and bool(coverage.get("target_columns_covered"))
    )
    if state == "OBSERVED" and kind == "RUNTIME_POSITIVE" and complete and status in ("", "SUPPORTED"):
        return "High"
    if kind in {"STATIC_DEPENDENCY", "DBT_DECLARED"} and status == "SUPPORTED":
        return "Medium"
    return "Low"
