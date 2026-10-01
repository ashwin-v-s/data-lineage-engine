"""
backend/app/api/routes/dependency.py
──────────────────────────────────────
Dependency state endpoint: pulls evidence from Supabase and runs
the FourStateEngine to return OBSERVED / POSSIBLE / REFUTED_FOR_RUN / UNKNOWN.

Endpoint
────────
  GET /api/v1/runs/{run_id}/dependency/{source}/{target}
      ?as_of=<ISO-8601>            valid-time snapshot   (default: now)
      ?recorded_as_of=<ISO-8601>   transaction-time      (default: now)
      ?granularity=DATASET|COLUMN  (default: COLUMN)

Path parameters
───────────────
  run_id   – the execution run identifier (matches execution_run.run_id)
  source   – source column UUID or name  (e.g. "order_id", or a UUID)
  target   – target column UUID or name

How it works
────────────
  1. Resolve source/target to column UUIDs via column_record (or dataset fallback)
  2. Pull STATIC_DEPENDENCY evidence for (source_col, target_col) with temporal filter
  3. Pull RUNTIME_POSITIVE / RUNTIME_NEGATIVE_EVALUATION evidence for this run
  4. Build PredictorInput and call FourStateEngine.infer()
  5. Return structured JSON with state + explanation + evidence refs

Graceful degradation
────────────────────
  If no evidence exists yet (M1 hasn't loaded data), the engine returns UNKNOWN (R5).
  The route returns 200 in all cases — 404 only if the run_id itself doesn't exist.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from backend.app.db import get_conn
from contracts.evidence import PredictorInput, RuntimeEvidence, StaticEvidence
from contracts.types import (
    CoverageMode,
    CoverageVector,
    DependencyKey,
    EvidenceType,
    Granularity,
    ParserStatus,
    PredictedState,
    TemporalContext,
)
from research.reasoning.engine import FourStateEngine

router = APIRouter()

# ── Response schema ───────────────────────────────────────────────────────────

class EvidenceRef(BaseModel):
    evidence_id: str
    evidence_type: str
    source_system: str
    event_time: Optional[str] = None

class CoverageOut(BaseModel):
    run_covered: bool
    operator_covered: bool
    source_dataset_covered: bool
    target_dataset_covered: bool
    branches_covered: bool
    coverage_mode: str
    parser_status: str

class DependencyStateResponse(BaseModel):
    run_id: str
    source: dict
    target: dict
    granularity: str
    state: str
    interpretation: str
    explanation: str
    rule_id: str
    reasoning_version: str
    flags: list[str]
    evidence: list[EvidenceRef]
    coverage: Optional[CoverageOut]
    temporal_context: dict
    is_mock: bool = False

# ── Locked interpretations (Section 4 of the pack) ───────────────────────────

_INTERPRETATIONS: dict[PredictedState, str] = {
    PredictedState.OBSERVED:
        "At least one source value was observed to contribute to a target output in this run.",
    PredictedState.REFUTED_FOR_RUN:
        "No propagation was established for this run under a declared complete negative evaluation.",
    PredictedState.POSSIBLE:
        "Static analysis permits this dependency, but runtime evidence is absent or incomplete.",
    PredictedState.UNKNOWN:
        "Insufficient information to determine the dependency state for this run.",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_column(cur, identifier: str, run_id: str) -> dict | None:
    """Resolve a column by UUID, name, or 'dataset.column' notation.
    Falls back to a dataset-level lookup if no column_record matches.
    Returns {id, display} or None.
    """
    import re
    uuid_re = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )

    # 1. Direct UUID match in column_record
    if uuid_re.match(identifier):
        cur.execute(
            """
            SELECT cr.id::text, cr.column_name,
                   d.name AS dataset_name
            FROM   column_record cr
            JOIN   dataset d ON d.id = cr.dataset_id
            WHERE  cr.id = %s::uuid
            LIMIT 1
            """,
            (identifier,)
        )
        row = cur.fetchone()
        if row:
            return {"id": row["id"], "display": f"{row['dataset_name']}.{row['column_name']}"}

        # Maybe it's a dataset UUID
        cur.execute(
            "SELECT id::text, name FROM dataset WHERE id = %s::uuid LIMIT 1",
            (identifier,)
        )
        row = cur.fetchone()
        if row:
            return {"id": row["id"], "display": row["name"]}

    # 2. Name-based: "dataset.column" notation
    if "." in identifier:
        parts = identifier.rsplit(".", 1)
        ds_name, col_name = parts[0], parts[1]
        cur.execute(
            """
            SELECT cr.id::text, cr.column_name, d.name AS dataset_name
            FROM   column_record cr
            JOIN   dataset d ON d.id = cr.dataset_id
            WHERE  lower(d.name) = lower(%s)
              AND  lower(cr.column_name) = lower(%s)
            LIMIT 1
            """,
            (ds_name, col_name)
        )
        row = cur.fetchone()
        if row:
            return {"id": row["id"], "display": f"{row['dataset_name']}.{row['column_name']}"}

    # 3. Plain column name search
    cur.execute(
        """
        SELECT cr.id::text, cr.column_name, d.name AS dataset_name
        FROM   column_record cr
        JOIN   dataset d ON d.id = cr.dataset_id
        WHERE  lower(cr.column_name) = lower(%s)
        LIMIT 1
        """,
        (identifier,)
    )
    row = cur.fetchone()
    if row:
        return {"id": row["id"], "display": f"{row['dataset_name']}.{row['column_name']}"}

    # 4. Dataset-level fallback (coarse DATASET granularity)
    cur.execute(
        """
        SELECT id::text, name
        FROM   dataset
        WHERE  lower(name) = lower(%s)
        ORDER BY created_at DESC LIMIT 1
        """,
        (identifier,)
    )
    row = cur.fetchone()
    if row:
        return {"id": row["id"], "display": row["name"]}

    return None


def _fetch_static_evidence(cur, source_id: str, target_id: str, granularity: str,
                            as_of: str, recorded_as_of: str) -> list[StaticEvidence]:
    """Pull STATIC_DEPENDENCY evidence for (source, target) with temporal filter."""
    cur.execute(
        """
        SELECT e.evidence_id, e.source_dataset_id, e.target_dataset_id,
               e.source_column_id, e.target_column_id,
               e.granularity, e.operator, e.query_fingerprint,
               e.schema_fingerprint, e.expression_fingerprint,
               e.parser_status, e.diagnostics,
               etv.valid_from, etv.valid_to,
               etv.transaction_from, etv.transaction_to
        FROM   evidence e
        -- join via lineage_edge to get bitemporal validity
        LEFT JOIN lineage_edge le
               ON (le.source_id = e.source_column_id OR le.source_id = e.source_dataset_id)
              AND (le.target_id = e.target_column_id OR le.target_id = e.target_dataset_id)
        LEFT JOIN edge_temporal_version etv ON etv.edge_id = le.id
               AND etv.valid_from  <= %s::timestamptz
               AND (etv.valid_to   IS NULL OR etv.valid_to  > %s::timestamptz)
               AND etv.transaction_from <= %s::timestamptz
               AND (etv.transaction_to  IS NULL OR etv.transaction_to > %s::timestamptz)
        WHERE  e.evidence_type = 'STATIC_DEPENDENCY'
          AND  (e.source_column_id  = %s::uuid OR e.source_dataset_id  = %s::uuid)
          AND  (e.target_column_id  = %s::uuid OR e.target_dataset_id  = %s::uuid)
          AND  e.granularity = %s
        """,
        (as_of, as_of, recorded_as_of, recorded_as_of,
         source_id, source_id, target_id, target_id, granularity)
    )
    rows = cur.fetchall()
    results = []
    for r in rows:
        try:
            se = StaticEvidence(
                evidence_id=r["evidence_id"],
                source_dataset_id=str(r["source_dataset_id"] or r["source_column_id"] or source_id),
                target_dataset_id=str(r["target_dataset_id"] or r["target_column_id"] or target_id),
                source_column_id=str(r["source_column_id"]) if r["source_column_id"] else None,
                target_column_id=str(r["target_column_id"]) if r["target_column_id"] else None,
                granularity=Granularity(r["granularity"]),
                operator=r["operator"] or "unknown",
                expression_fingerprint=r["expression_fingerprint"] or "",
                query_fingerprint=r["query_fingerprint"] or "",
                schema_fingerprint=r["schema_fingerprint"] or "",
                parser_status=ParserStatus(r["parser_status"]) if r["parser_status"] else ParserStatus.UNSUPPORTED,
                diagnostics=tuple(r["diagnostics"] or []),
            )
            results.append(se)
        except Exception:
            continue
    return results


def _fetch_runtime_evidence(cur, run_id: str, source_id: str, target_id: str,
                             granularity: str, as_of: str, recorded_as_of: str) -> list[RuntimeEvidence]:
    """Pull runtime evidence for this specific run + (source, target)."""
    cur.execute(
        """
        SELECT e.evidence_id, e.evidence_type, e.source_system,
               e.event_time, e.run_id,
               e.source_column_id, e.target_column_id,
               e.granularity, e.coverage,
               e.parser_status, e.operator
        FROM   evidence e
        WHERE  e.run_id = %s
          AND  e.evidence_type IN ('RUNTIME_POSITIVE', 'RUNTIME_NEGATIVE_EVALUATION')
          AND  (e.source_column_id  = %s::uuid OR e.source_dataset_id  = %s::uuid)
          AND  (e.target_column_id  = %s::uuid OR e.target_dataset_id  = %s::uuid)
          AND  e.granularity = %s
          AND  e.ingestion_time <= %s::timestamptz
        """,
        (run_id,
         source_id, source_id, target_id, target_id,
         granularity, recorded_as_of)
    )
    rows = cur.fetchall()
    results = []
    key = DependencyKey(
        run_id=run_id,
        source_column_id=source_id,
        target_column_id=target_id,
        granularity=Granularity(granularity),
    )

    for r in rows:
        raw_cov = r["coverage"]
        if isinstance(raw_cov, str):
            raw_cov = json.loads(raw_cov)

        # Build a minimal CoverageVector from the stored JSON or defaults
        if raw_cov and isinstance(raw_cov, dict):
            cov = CoverageVector(
                run_covered=raw_cov.get("run_covered", True),
                operator_covered=raw_cov.get("operator_covered", True),
                source_dataset_covered=raw_cov.get("source_dataset_covered", True),
                target_dataset_covered=raw_cov.get("target_dataset_covered", True),
                source_columns_covered=tuple(raw_cov.get("source_columns_covered", [source_id])),
                target_columns_covered=tuple(raw_cov.get("target_columns_covered", [target_id])),
                branches_covered=raw_cov.get("branches_covered", True),
                coverage_mode=CoverageMode(raw_cov.get("coverage_mode", CoverageMode.RUNTIME)),
                parser_status=ParserStatus(raw_cov.get("parser_status", ParserStatus.SUPPORTED)),
            )
        else:
            # Runtime evidence without stored coverage: treat as structural-mode positive
            cov = CoverageVector(
                run_covered=True,
                operator_covered=True,
                source_dataset_covered=True,
                target_dataset_covered=True,
                source_columns_covered=(source_id,),
                target_columns_covered=(target_id,),
                branches_covered=True,
                coverage_mode=CoverageMode.RUNTIME,
                parser_status=ParserStatus.SUPPORTED,
            )

        try:
            re_obj = RuntimeEvidence(
                evidence_id=r["evidence_id"],
                evidence_type=EvidenceType(r["evidence_type"]),
                key=key,
                source_system=r["source_system"] or "unknown",
                event_time=r["event_time"].isoformat() if r["event_time"] else as_of,
                coverage=cov,
                raw_payload_hash="",
            )
            results.append(re_obj)
        except Exception:
            continue
    return results


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/runs/{run_id}/dependency/{source}/{target}",
    response_model=DependencyStateResponse,
    tags=["Reasoning"],
)
def get_dependency_state(
    run_id: str,
    source: str,
    target: str,
    as_of: Optional[str] = Query(default=None),
    recorded_as_of: Optional[str] = Query(default=None),
    granularity: str = Query(default="COLUMN", pattern="^(DATASET|COLUMN)$"),
):
    ts_as_of = as_of or _now_utc()
    ts_rec   = recorded_as_of or _now_utc()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Verify run exists
            cur.execute(
                "SELECT run_id, status FROM execution_run WHERE run_id = %s LIMIT 1",
                (run_id,)
            )
            run_row = cur.fetchone()
            if not run_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run '{run_id}' not found."
                )

            # 2. Resolve source and target identifiers
            src = _resolve_column(cur, source, run_id)
            tgt = _resolve_column(cur, target, run_id)

            src_id = src["id"] if src else source
            tgt_id = tgt["id"] if tgt else target
            src_display = src["display"] if src else source
            tgt_display = tgt["display"] if tgt else target

            # 3. Fetch evidence
            static_ev  = _fetch_static_evidence(cur, src_id, tgt_id, granularity, ts_as_of, ts_rec)
            runtime_ev = _fetch_runtime_evidence(cur, run_id, src_id, tgt_id, granularity, ts_as_of, ts_rec)

    # 4. Build DependencyKey + PredictorInput
    key = DependencyKey(
        run_id=run_id,
        source_column_id=src_id,
        target_column_id=tgt_id,
        granularity=Granularity(granularity),
        temporal_context=TemporalContext(
            valid_at=ts_as_of,
            known_as_of=ts_rec,
        ),
    )

    predictor_input = PredictorInput(
        keys=(key,),
        static_evidence=tuple(static_ev),
        runtime_evidence=tuple(runtime_ev),
        temporal_context=TemporalContext(valid_at=ts_as_of, known_as_of=ts_rec),
    )

    # 5. Run the FourStateEngine
    engine = FourStateEngine(enable_refutation=True)
    predictions = engine.infer(predictor_input)
    pred = predictions[0]

    # 6. Build evidence refs
    ev_lookup: dict[str, dict] = {}
    for se in static_ev:
        ev_lookup[se.evidence_id] = {
            "evidence_id": se.evidence_id,
            "evidence_type": "STATIC_DEPENDENCY",
            "source_system": "kairos",
            "event_time": None,
        }
    for re_obj in runtime_ev:
        ev_lookup[re_obj.evidence_id] = {
            "evidence_id": re_obj.evidence_id,
            "evidence_type": re_obj.evidence_type.value,
            "source_system": re_obj.source_system,
            "event_time": re_obj.event_time,
        }

    evidence_refs = [
        EvidenceRef(**ev_lookup[eid])
        for eid in pred.evidence_ids
        if eid in ev_lookup
    ]

    # 7. Build coverage output
    cov_out = None
    if pred.coverage:
        cov_out = CoverageOut(
            run_covered=pred.coverage.run_covered,
            operator_covered=pred.coverage.operator_covered,
            source_dataset_covered=pred.coverage.source_dataset_covered,
            target_dataset_covered=pred.coverage.target_dataset_covered,
            branches_covered=pred.coverage.branches_covered,
            coverage_mode=pred.coverage.coverage_mode.value,
            parser_status=pred.coverage.parser_status.value,
        )

    return DependencyStateResponse(
        run_id=run_id,
        source={"column_id": src_id, "display": src_display},
        target={"column_id": tgt_id, "display": tgt_display},
        granularity=granularity,
        state=pred.state.value,
        interpretation=_INTERPRETATIONS[pred.state],
        explanation=pred.explanation,
        rule_id=pred.rule_id,
        reasoning_version=pred.reasoning_version,
        flags=list(pred.flags),
        evidence=evidence_refs,
        coverage=cov_out,
        temporal_context={"as_of": ts_as_of, "recorded_as_of": ts_rec},
        is_mock=False,
    )
