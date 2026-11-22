"""Evidence-based state and coverage for one lineage relationship.

This module answers two separate questions about an edge, and never mixes them:

    state     what the stored evidence permits us to claim
              (OBSERVED | REFUTED_FOR_RUN | POSSIBLE | UNKNOWN)
    coverage  how much of the relationship the evidence actually spans
              (COMPLETE | PARTIAL | NONE)

Neither value is a probability, a confidence or a quality score. They are
rule-derived labels over the evidence rows that a workspace has stored, and
they are computed at read time so an edge can never carry a stale claim.

Rules
-----
state, in precedence order:

    REFUTED_FOR_RUN   a run-scoped negative evaluation exists and no positive
                      runtime observation does. It is never a universal claim.
    OBSERVED          at least one RUNTIME_POSITIVE observation exists.
    POSSIBLE          only static/declared evidence exists (SQL, dbt, import).
    UNKNOWN           nothing is stored. Absence is not refutation.

coverage, in precedence order:

    COMPLETE          a runtime observation whose coverage is complete *for the
                      granularity being asserted* (see below).
    PARTIAL           some evidence exists (static only, or runtime with an
                      incomplete coverage manifest).
    NONE              no evidence is attached.

Granularity scoping
-------------------
Coverage is only "complete" with respect to what the edge claims. A DATASET
edge asserts that the job boundary read the source dataset and wrote the target
dataset; operator, branch and column dimensions describe finer claims that the
dataset edge does not make, so they are reported as not applicable rather than
as missing. A COLUMN edge does assert column/operator/branch scope, so those
dimensions must all be covered before it can be called complete.

This is the only reason a dataset-level OpenLineage observation can be
COMPLETE: it is complete for the claim it makes, and its diagnostic states
that column-level lineage was not parsed.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

COVERAGE_RULE_VERSION = "kairos.coverage.v1"

STATE_OBSERVED = "OBSERVED"
STATE_REFUTED = "REFUTED_FOR_RUN"
STATE_POSSIBLE = "POSSIBLE"
STATE_UNKNOWN = "UNKNOWN"

COVERAGE_COMPLETE = "COMPLETE"
COVERAGE_PARTIAL = "PARTIAL"
COVERAGE_NONE = "NONE"

SOURCE_SQL = "SQL"
SOURCE_DBT = "DBT_MANIFEST"
SOURCE_RUNTIME = "OPENLINEAGE"
SOURCE_OTHER = "OTHER"

_STATE_PRECEDENCE = {
    STATE_OBSERVED: 0,
    STATE_REFUTED: 1,
    STATE_POSSIBLE: 2,
    STATE_UNKNOWN: 3,
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def runtime_coverage_complete(coverage: Any, granularity: str = "DATASET") -> bool:
    """Whether a runtime coverage manifest is complete for this granularity.

    A manifest that is not explicitly ``coverage_mode == "runtime"`` is never
    complete, however many of its booleans happen to be true.
    """
    cov = _as_mapping(coverage)
    if str(cov.get("coverage_mode", "")).strip().lower() != "runtime":
        return False
    if cov.get("run_covered") is not True:
        return False
    scope = str(cov.get("scope") or granularity or "DATASET").upper()
    if scope == "COLUMN":
        required = ("operator_covered", "source_dataset_covered",
                    "target_dataset_covered", "branches_covered")
        if not all(cov.get(key) is True for key in required):
            return False
        return bool(cov.get("source_columns_covered")) and bool(cov.get("target_columns_covered"))
    # DATASET scope: the boundary the edge asserts is in/out dataset coverage.
    return (cov.get("source_dataset_covered") is True
            and cov.get("target_dataset_covered") is True)


def evidence_source(
    evidence_type: Any,
    source_system: Any = None,
    diagnostics: Any = None,
) -> str:
    """Map a stored evidence row onto the provenance family it came from."""
    kind = str(evidence_type or "").strip().upper()
    system = str(source_system or "").strip().lower()
    if kind.startswith("RUNTIME"):
        return SOURCE_RUNTIME
    if kind == "DBT_DECLARED":
        return SOURCE_DBT
    if kind == "STATIC_DEPENDENCY":
        diag = _as_mapping(diagnostics)
        edge_type = str(diag.get("edge_type") or "").strip().lower()
        if edge_type in {"declared_dependency", "ref", "source", "dbt_declared"}:
            return SOURCE_DBT
        if system in {"dbt", "dbt_manifest"}:
            return SOURCE_DBT
        return SOURCE_SQL
    if kind:
        return SOURCE_OTHER
    return SOURCE_OTHER


def state_for_evidence_type(evidence_type: Any) -> str:
    """The state a single evidence row permits on its own.

    One row can only support the claim its own type makes: a runtime
    observation is OBSERVED, a declared or static relationship is POSSIBLE, a
    run-scoped negative evaluation is REFUTED_FOR_RUN. Anything else is
    UNKNOWN. Aggregate precedence lives in :func:`aggregate_edge_evidence`.

    This is the single source of truth for that mapping; SQL read models and
    the edge aggregate both use it, so a row can never be labelled one way on
    the graph and another way in the inspector.
    """
    kind = str(evidence_type or "").strip().upper()
    if kind == "RUNTIME_POSITIVE":
        return STATE_OBSERVED
    if kind == "RUNTIME_NEGATIVE_EVALUATION":
        return STATE_REFUTED
    if kind in {"STATIC_DEPENDENCY", "DBT_DECLARED"}:
        return STATE_POSSIBLE
    return STATE_UNKNOWN


def _state_for(rows: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    states = [state_for_evidence_type(row.get("evidence_type")) for row in rows]
    if STATE_OBSERVED in states:
        return STATE_OBSERVED, "A runtime event observed this relationship directly."
    if STATE_REFUTED in states:
        return STATE_REFUTED, (
            "A declared complete negative evaluation is recorded for one run. "
            "This is run-scoped and is not a universal refutation."
        )
    if STATE_POSSIBLE in states:
        return STATE_POSSIBLE, (
            "Only static or declared evidence is stored; propagation is not proven."
        )
    return STATE_UNKNOWN, "No evidence is stored for this relationship."


def aggregate_edge_evidence(
    rows: Iterable[Mapping[str, Any]],
    granularity: str = "DATASET",
) -> dict[str, Any]:
    """Return the rule-derived state, coverage and provenance for one edge.

    ``rows`` are evidence rows (or row mappings) carrying at least
    ``evidence_type``; ``coverage``, ``source_system``, ``diagnostics``,
    ``run_id`` and ``event_time`` are used when present.
    """
    materialised: list[Mapping[str, Any]] = [row for row in rows]
    sources: list[str] = []
    basis: list[str] = []
    runtime_complete = False
    runtime_present = False
    latest_event_time = None
    run_ids: set[str] = set()

    for row in materialised:
        source = evidence_source(
            row.get("evidence_type"),
            row.get("source_system"),
            row.get("diagnostics"),
        )
        if source not in sources:
            sources.append(source)
        kind = str(row.get("evidence_type") or "").upper()
        if kind.startswith("RUNTIME"):
            runtime_present = True
            if runtime_coverage_complete(row.get("coverage"), granularity):
                runtime_complete = True
        run_id = row.get("run_id")
        if run_id:
            run_ids.add(str(run_id))
        event_time = row.get("event_time")
        if event_time is not None:
            text = event_time.isoformat() if hasattr(event_time, "isoformat") else str(event_time)
            if latest_event_time is None or text > latest_event_time:
                latest_event_time = text

    for source in sources:
        if source == SOURCE_RUNTIME:
            basis.append("OPENLINEAGE_RUNTIME")
        elif source == SOURCE_DBT:
            basis.append("DBT_DECLARED")
        elif source == SOURCE_SQL:
            basis.append("SQL_STATIC")
        else:
            basis.append("OTHER_EVIDENCE")

    if not materialised:
        state, state_reason = STATE_UNKNOWN, "No evidence is stored for this relationship."
    else:
        state, state_reason = _state_for(materialised)

    if runtime_complete:
        coverage = COVERAGE_COMPLETE
    elif runtime_present or any(
        str(row.get("evidence_type") or "").upper() in {"STATIC_DEPENDENCY", "DBT_DECLARED"}
        for row in materialised
    ):
        coverage = COVERAGE_PARTIAL
    else:
        coverage = COVERAGE_NONE

    return {
        "state": state,
        "state_reason": state_reason,
        "coverage": coverage,
        "coverage_basis": sorted(basis),
        "coverage_scope": str(granularity or "DATASET").upper(),
        "evidence_sources": sorted(sources),
        "evidence_count": len(materialised),
        "run_count": len(run_ids),
        "latest_event_time": latest_event_time,
        "coverage_rule_version": COVERAGE_RULE_VERSION,
    }


def strongest_state(states: Iterable[str]) -> str:
    """Pick the most informative state from several connecting edges."""
    ranked = sorted(
        (str(state or STATE_UNKNOWN).upper() for state in states),
        key=lambda state: _STATE_PRECEDENCE.get(state, _STATE_PRECEDENCE[STATE_UNKNOWN]),
    )
    return ranked[0] if ranked else STATE_UNKNOWN
