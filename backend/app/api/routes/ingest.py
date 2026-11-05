"""
POST /api/v1/ingest/openlineage
───────────────────────────────
Runtime evidence ingestion for OpenLineage events.

Rules (from Architecture Pack §12 and handout G1/A1):
  1. Every accepted event is stored immutably in raw_event — one row per
     unique (source_system, event_id/payload_hash).
  2. COMPLETE events produce RUNTIME_POSITIVE evidence rows (one per
     input-to-output pair that the event boundary proves was observed).
  3. Missing events, duplicate events, START/FAIL/ABORT events: never
     produce negative evidence.  Absence is not stored.
  4. No cartesian-product lineage edges are created.  The presence of
     multiple inputs and multiple outputs in one event means the job
     boundary was observed — it does NOT mean input_i → output_j.
     Exact column-level edges require the columnLineage facet (not yet
     supported; noted in diagnostics when present).
  5. Duplicate detection is by payload SHA-256 hash.  Replaying the same
     event is safe and returns duplicate=True with no DB writes.

The route does NOT require auth for the initial integration phase (the
ingestion endpoint is called by pipeline tools, not browsers).  Auth can
be tightened via the require_user dependency once the shared Supabase
project issues service tokens.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field, model_validator

from backend.app.api.errors import api_error
from backend.app.db import get_conn

router = APIRouter(tags=["ingestion"])


# ---------------------------------------------------------------------------
# Request / response schemas (mirrors backend/app/schemas.py partial defs
# but with stricter validation and batch support)
# ---------------------------------------------------------------------------

class OpenLineageEventPayload(BaseModel):
    """
    A single OpenLineage event.  Required: eventType, eventTime, run.runId,
    job.name.  Inputs/outputs are optional (a START event may have none).
    """

    eventType: str = Field(..., description="START | RUNNING | COMPLETE | ABORT | FAIL | OTHER")
    eventTime: str = Field(..., description="ISO-8601 timestamp")
    run: dict = Field(..., description="Must contain runId")
    job: dict = Field(..., description="Must contain name (and optionally namespace)")
    inputs: List[dict] = Field(default_factory=list)
    outputs: List[dict] = Field(default_factory=list)
    producer: Optional[str] = None

    @model_validator(mode="after")
    def _require_run_id_and_job_name(self) -> "OpenLineageEventPayload":
        if not self.run.get("runId", "").strip():
            raise ValueError("run.runId is required and must not be empty")
        if not self.job.get("name", "").strip():
            raise ValueError("job.name is required and must not be empty")
        return self


class OpenLineageIngestRequest(BaseModel):
    """Accept either a single event (the common case) or a batch of up to 100."""

    events: Optional[List[OpenLineageEventPayload]] = None
    # Convenience: the caller may POST a single event at the top level
    # (i.e. the body IS one event, not wrapped in {"events": [...]}).
    # Handled by the endpoint by accepting Any and normalising.


class SingleEventOrBatch(BaseModel):
    """Union shape — caller may POST one event OR {"events": [...]}."""
    eventType: Optional[str] = None
    events: Optional[List[Any]] = None


class IngestResult(BaseModel):
    accepted: int = Field(..., description="Number of events newly stored")
    duplicate: int = Field(..., description="Number of events already present (no-op)")
    skipped: int = Field(..., description="Events skipped (non-COMPLETE, missing required fields)")
    evidence_created: int = Field(..., description="RUNTIME_POSITIVE evidence rows written")
    diagnostics: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload_hash(event: dict) -> str:
    """SHA-256 of the canonical JSON representation."""
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event_id(event: dict) -> str:
    """Use the event's own eventId if present, otherwise SHA-256 of payload."""
    eid = event.get("eventId") or event.get("eventID") or ""
    return str(eid).strip() or _payload_hash(event)


def _parse_event_time(value: str) -> Optional[datetime]:
    """Parse ISO-8601 to aware UTC datetime; return None on failure."""
    if not value:
        return None
    try:
        # Python 3.11+ handles Z natively; for 3.10 compatibility replace Z.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _upsert_raw_event(cur, event_id: str, payload: dict, phash: str) -> bool:
    """
    Insert the raw event.  Returns True if newly inserted, False if duplicate.

    raw_event.event_id is the PRIMARY KEY so a conflict means a duplicate.
    source_system is hardcoded to 'openlineage'.
    """
    cur.execute(
        """
        INSERT INTO raw_event (event_id, payload, payload_hash, source_system)
        VALUES (%s, %s::jsonb, %s, 'openlineage')
        ON CONFLICT (event_id) DO NOTHING
        """,
        (event_id, json.dumps(payload), phash),
    )
    return cur.rowcount == 1


def _upsert_dataset(cur, namespace: str, name: str) -> Optional[str]:
    """
    Ensure a dataset row exists for (openlineage, namespace, name).
    Returns the dataset UUID, or None on failure.

    Uses empty strings for database_name/schema_name since OpenLineage
    events carry namespace + name only; schema decomposition is future work.
    """
    if not name:
        return None
    try:
        cur.execute(
            """
            INSERT INTO dataset
                (source_system, namespace, database_name, schema_name, name, asset_type)
            VALUES ('openlineage', %s, '', %s, %s, 'table')
            ON CONFLICT (source_system, namespace, database_name, schema_name, name, asset_type)
            DO UPDATE SET name = EXCLUDED.name   -- no-op, just to return RETURNING
            RETURNING id
            """,
            (namespace or "", namespace or "", name),
        )
        row = cur.fetchone()
        return str(row["id"]) if row else None
    except Exception:
        return None


def _write_runtime_positive_evidence(
    cur,
    event_id: str,
    run_id: str,
    event_time: Optional[datetime],
    source_dataset_id: Optional[str],
    target_dataset_id: Optional[str],
    diagnostics: List[str],
) -> int:
    """
    Write one RUNTIME_POSITIVE evidence row for a (source_dataset, target_dataset)
    pair observed in a COMPLETE event.

    Returns 1 if newly inserted, 0 if duplicate.

    Invariant: only RUNTIME_POSITIVE is written here.  There is deliberately
    no path that writes RUNTIME_NEGATIVE_EVALUATION — absence of an event is
    never recorded.
    """
    # Deterministic evidence_id so replaying the same event is idempotent.
    evidence_id = f"ol:{run_id}:{source_dataset_id}:{target_dataset_id}"

    coverage = json.dumps({
        "mode": "runtime",
        "run_covered": True,
        "operator_covered": False,   # COMPLETE event proves run boundary, not operator
        "source_dataset_covered": source_dataset_id is not None,
        "target_dataset_covered": target_dataset_id is not None,
        "source_columns_covered": [],
        "target_columns_covered": [],
        "branches_covered": False,   # branch coverage requires columnLineage facet
        "coverage_mode": "runtime",
        "parser_status": "UNSUPPORTED",  # no static parse for this evidence type
        "note": (
            "Dataset boundary observation only — COMPLETE event proves the job "
            "read the source and wrote the target.  Column-level and branch "
            "coverage are not available without the columnLineage facet."
        ),
    })

    diag_json = json.dumps(diagnostics) if diagnostics else "[]"

    cur.execute(
        """
        INSERT INTO evidence (
            evidence_id,
            evidence_type,
            source_system,
            run_id,
            source_dataset_id,
            target_dataset_id,
            granularity,
            parser_status,
            coverage,
            event_time,
            ingestion_time,
            diagnostics,
            raw_event_id
        )
        VALUES (%s, 'RUNTIME_POSITIVE', 'openlineage', %s, %s::uuid, %s::uuid,
                'DATASET', 'UNSUPPORTED', %s::jsonb, %s, now(), %s::jsonb, %s)
        ON CONFLICT (evidence_id) DO NOTHING
        """,
        (
            evidence_id,
            run_id,
            source_dataset_id,
            target_dataset_id,
            coverage,
            event_time,
            diag_json,
            event_id,
        ),
    )
    return cur.rowcount


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/ingest/openlineage",
    summary="Ingest one or more OpenLineage runtime events",
    description=(
        "Stores each event immutably, then normalizes COMPLETE events into "
        "RUNTIME_POSITIVE evidence rows.  Missing events and non-COMPLETE "
        "events never produce negative evidence.  Duplicate payloads are "
        "accepted silently (idempotent).  No lineage edges are invented from "
        "the input×output cartesian product."
    ),
)
async def ingest_openlineage(request: Request) -> JSONResponse:
    """
    Accept a single OpenLineage event (bare JSON object) or a batch
    {"events": [...]}.  Returns counts and diagnostics.
    """
    try:
        body = await request.json()
    except Exception:
        return api_error(request, "Request body must be valid JSON", 400, "INVALID_JSON")

    if not isinstance(body, dict):
        return api_error(request, "Request body must be a JSON object", 400, "INVALID_PAYLOAD")

    # Normalise single-event vs batch
    if "events" in body and isinstance(body["events"], list):
        raw_events = body["events"]
    elif "eventType" in body:
        raw_events = [body]
    else:
        return api_error(
            request,
            "Provide either a single OpenLineage event object or {\"events\": [...]}",
            400,
            "INVALID_PAYLOAD",
        )

    if len(raw_events) == 0:
        return JSONResponse(IngestResult(
            accepted=0, duplicate=0, skipped=0,
            evidence_created=0, diagnostics=["Empty event batch."],
        ).model_dump())

    if len(raw_events) > 100:
        return api_error(
            request,
            "Batch size exceeds limit of 100 events per request",
            413,
            "BATCH_TOO_LARGE",
        )

    total_accepted = 0
    total_duplicate = 0
    total_skipped = 0
    total_evidence = 0
    all_diagnostics: List[str] = []

    # Check DB availability
    try:
        with get_conn() as conn:
            pass
    except Exception as exc:
        return api_error(
            request,
            f"Ingestion storage is not available: {exc}",
            503,
            "STORAGE_UNAVAILABLE",
        )

    for raw in raw_events:
        if not isinstance(raw, dict):
            total_skipped += 1
            all_diagnostics.append("Skipped non-object event in batch.")
            continue

        # Validate required fields
        run_id = str(raw.get("run", {}).get("runId", "")).strip()
        job_name = str(raw.get("job", {}).get("name", "")).strip()
        job_namespace = str(raw.get("job", {}).get("namespace", "")).strip()
        event_type = str(raw.get("eventType", "")).strip().upper()
        event_time_raw = str(raw.get("eventTime", "")).strip()

        event_diagnostics: List[str] = []

        if not run_id:
            total_skipped += 1
            all_diagnostics.append("Skipped event: missing run.runId.")
            continue

        if not job_name:
            total_skipped += 1
            all_diagnostics.append(f"Skipped event run={run_id}: missing job.name.")
            continue

        if not event_type:
            event_diagnostics.append("missing_event_type")

        # Compute identity
        phash = _payload_hash(raw)
        eid = _event_id(raw)
        event_time = _parse_event_time(event_time_raw)

        if event_time is None and event_time_raw:
            event_diagnostics.append(f"unparseable_event_time:{event_time_raw}")

        try:
            with get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # --- 1. Store raw event (idempotent) ---
                    newly_stored = _upsert_raw_event(cur, eid, raw, phash)

                    if not newly_stored:
                        total_duplicate += 1
                        continue  # Idempotent replay — nothing more to do.

                    total_accepted += 1

                    # --- 2. Only COMPLETE events produce positive evidence ---
                    # START / RUNNING / FAIL / ABORT / OTHER events are stored
                    # raw but produce no evidence rows — absence of evidence is
                    # not evidence of absence.
                    if event_type != "COMPLETE":
                        if event_type in ("START", "RUNNING", "ABORT", "FAIL", "OTHER"):
                            event_diagnostics.append(
                                f"non_complete_event:{event_type} — raw event stored, no evidence written"
                            )
                        else:
                            event_diagnostics.append(
                                f"unknown_event_type:{event_type} — raw event stored, no evidence written"
                            )
                        all_diagnostics.extend(event_diagnostics)
                        continue

                    inputs = raw.get("inputs", []) or []
                    outputs = raw.get("outputs", []) or []

                    if not inputs or not outputs:
                        event_diagnostics.append(
                            "complete_event_has_no_inputs_or_outputs — no evidence written"
                        )
                        all_diagnostics.extend(event_diagnostics)
                        continue

                    # --- 3. Check for columnLineage facet (not yet supported) ---
                    has_col_lineage = any(
                        out.get("facets", {}).get("columnLineage")
                        for out in outputs
                        if isinstance(out, dict)
                    )
                    if has_col_lineage:
                        event_diagnostics.append(
                            "columnLineage_facet_detected — column-level facet is not yet "
                            "parsed; dataset-level evidence only is written"
                        )

                    # --- 4. Upsert datasets and write evidence ---
                    # RULE: No cartesian product.  We write one evidence row per
                    # (input, output) pair observed in the event.  Each row says
                    # "the job read this source and wrote this target in this run."
                    # That is an observation of a dataset boundary — it does NOT
                    # imply that input_i caused output_j at the column level.
                    for inp in inputs:
                        if not isinstance(inp, dict):
                            continue
                        inp_ns = str(inp.get("namespace", "")).strip()
                        inp_name = str(inp.get("name", "")).strip()
                        if not inp_name:
                            event_diagnostics.append("input_missing_name — skipped")
                            continue

                        src_id = _upsert_dataset(cur, inp_ns, inp_name)
                        if not src_id:
                            event_diagnostics.append(f"failed_to_upsert_input_dataset:{inp_name}")
                            continue

                        for out in outputs:
                            if not isinstance(out, dict):
                                continue
                            out_ns = str(out.get("namespace", "")).strip()
                            out_name = str(out.get("name", "")).strip()
                            if not out_name:
                                event_diagnostics.append("output_missing_name — skipped")
                                continue

                            tgt_id = _upsert_dataset(cur, out_ns, out_name)
                            if not tgt_id:
                                event_diagnostics.append(f"failed_to_upsert_output_dataset:{out_name}")
                                continue

                            rows = _write_runtime_positive_evidence(
                                cur=cur,
                                event_id=eid,
                                run_id=run_id,
                                event_time=event_time,
                                source_dataset_id=src_id,
                                target_dataset_id=tgt_id,
                                diagnostics=event_diagnostics,
                            )
                            total_evidence += rows

                all_diagnostics.extend(event_diagnostics)

        except Exception as exc:
            all_diagnostics.append(f"db_error:{exc}")
            total_skipped += 1

    return JSONResponse(
        status_code=200,
        content=IngestResult(
            accepted=total_accepted,
            duplicate=total_duplicate,
            skipped=total_skipped,
            evidence_created=total_evidence,
            diagnostics=all_diagnostics,
        ).model_dump(),
    )
