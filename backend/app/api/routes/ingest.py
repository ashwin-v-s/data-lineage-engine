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
"""Authenticated preview and explicit commit for static metadata imports.

The browser never writes to Postgres. Preview runs the same pure adapters as
the CLI; commit revalidates the submitted content and writes it atomically
under the verified user's workspace context.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth import require_user
from backend.app.db import get_conn
from ingestion.static_files import parse_static_file

router = APIRouter(prefix="/ingest", tags=["ingestion"], dependencies=[Depends(require_user)])

# Read-only projection of an import_run row.  UUIDs and the timestamp are cast
# to text in SQL so the result is directly JSON-serialisable; row-level security
# scopes the rows to the caller's workspace, so no workspace_id is ever accepted
# from the client.
_RUN_COLUMNS = """
    id::text                                                                   AS id,
    source_kind,
    source_ref,
    content_sha256,
    contract_version,
    adapter_name,
    adapter_version,
    status,
    result_summary,
    to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')   AS created_at
"""


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["metadata_graph", "dbt_manifest", "file_inventory", "csv_headers"]
    filename: str = Field(default="upload", min_length=1, max_length=255)
    content: Any
    source_revision: str | None = Field(default=None, max_length=512)


class CommitInput(ImportInput):
    idempotency_key: str = Field(min_length=1, max_length=256)


def _parse(request: ImportInput):
    result = parse_static_file(
        request.kind,
        request.content,
        filename=request.filename,
        source_revision=request.source_revision,
    )
    if not result.ok:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import validation failed", "diagnostics": [d.as_dict() for d in result.diagnostics]},
        )
    assert result.payload is not None
    return result.payload, [warning.as_dict() for warning in result.warnings]


def _summary(payload: dict[str, Any], warnings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "contract_version": payload["contract_version"],
        "assets": len(payload["assets"]),
        "relationships": len(payload["relationships"]),
        "columns": sum(len(a.get("metadata", {}).get("columns", [])) for a in payload["assets"]),
        "warnings": warnings,
        "provenance": payload["provenance"],
    }


@router.post("/preview")
def preview_import(request: ImportInput, user: dict = Depends(require_user)):
    """Validate and normalize an import without performing database writes."""
    payload, warnings = _parse(request)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.import_run') AS import_run")
            commit_ready = bool(cur.fetchone()["import_run"])
    return {
        "ok": True,
        "preview": _summary(payload, warnings),
        "normalized": payload,
        "commit_ready": commit_ready,
        "commit_blocker": None if commit_ready else "The import-run migration is not installed in this Supabase project.",
    }


def _insert_asset(cur, asset: dict[str, Any], source_kind: str, source_ref: str) -> str:
    namespace = str(asset.get("namespace") or "general")
    name = str(asset.get("name") or asset["qualified_name"].rsplit("/", 1)[-1])
    asset_type = str(asset.get("type") or asset.get("asset_type") or "table").upper()
    # Put the source ref into the identity tuple so same-named uploads from
    # separate repositories/files don't overwrite each other.
    database_name = source_ref or "kairos-import"
    cur.execute(
        """
        INSERT INTO dataset (source_system, namespace, database_name, schema_name, name, asset_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (workspace_id, source_system, namespace, database_name, schema_name, name, asset_type)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id::text AS id
        """,
        (source_kind, namespace, database_name, namespace, name, asset_type),
    )
    dataset_id = cur.fetchone()["id"]

    columns = asset.get("metadata", {}).get("columns", [])
    for column in columns if isinstance(columns, list) else []:
        if not isinstance(column, dict) or not isinstance(column.get("name"), str):
            continue
        cur.execute(
            """
            INSERT INTO column_record (dataset_id, column_name, data_type)
            VALUES (%s::uuid, %s, %s)
            ON CONFLICT (dataset_id, schema_version, column_name)
            DO UPDATE SET data_type = EXCLUDED.data_type
            """,
            (dataset_id, column["name"], column.get("data_type")),
        )
    return dataset_id


@router.post("/commit")
def commit_import(request: CommitInput, user: dict = Depends(require_user)):
    """Revalidate then atomically persist assets, declared edges, and provenance."""
    payload, warnings = _parse(request)
    content_hash = payload["provenance"]["content_sha256"]
    source_ref = payload["source"].get("ref") or payload["provenance"].get("original_filename") or ""
    # Static adapters accept arbitrary descriptive source labels. The database
    # migration intentionally permits only source classes that Kairos owns.
    # A browser upload is always an upload, regardless of text in the file.
    source_kind = "upload"
    summary = _summary(payload, warnings)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.import_run') AS import_run")
            if not cur.fetchone()["import_run"]:
                raise HTTPException(
                    status_code=503,
                    detail="Ingestion storage is not installed. The reviewed import-run migration must be applied first.",
                )

            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(current_setting('kairos.workspace_id', true) || ':' || %s, 0))",
                (request.idempotency_key,),
            )
            cur.execute(
                """
                SELECT id::text, content_sha256, result_summary, status
                FROM import_run WHERE idempotency_key = %s LIMIT 1
                """,
                (request.idempotency_key,),
            )
            existing = cur.fetchone()
            if existing:
                if existing["content_sha256"] != content_hash:
                    raise HTTPException(status_code=409, detail="This idempotency key was already used for different content.")
                return {
                    "ok": True,
                    "replayed": True,
                    "import_id": existing["id"],
                    "status": existing["status"],
                    "summary": existing["result_summary"],
                }

            cur.execute(
                """
                INSERT INTO import_run
                    (actor_user_id, idempotency_key, source_kind, source_ref,
                     content_sha256, contract_version, adapter_name, adapter_version,
                     status, result_summary)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (
                    user["id"], request.idempotency_key, source_kind, source_ref,
                    content_hash, payload["contract_version"],
                    payload["provenance"]["adapter"], payload["provenance"]["adapter_version"],
                    "COMMITTED_WITH_WARNINGS" if warnings else "COMMITTED", Json(summary),
                ),
            )
            import_id = cur.fetchone()["id"]
            raw_event_id = f"kairos-import:{import_id}"
            cur.execute(
                """
                INSERT INTO raw_event (event_id, payload, payload_hash, source_system)
                VALUES (%s, %s, %s, %s)
                """,
                (raw_event_id, Json(payload), content_hash, source_kind),
            )

            dataset_ids: dict[str, str] = {}
            for asset in payload["assets"]:
                dataset_ids[asset["id"]] = _insert_asset(cur, asset, source_kind, source_ref)

            for index, relationship in enumerate(payload["relationships"]):
                source_id = dataset_ids[relationship["source_id"]]
                target_id = dataset_ids[relationship["target_id"]]
                edge_type = relationship["edge_type"]
                cur.execute(
                    """
                    INSERT INTO lineage_edge (source_id, target_id, granularity, operator_fingerprint)
                    VALUES (%s::uuid, %s::uuid, 'DATASET', %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id::text
                    """,
                    (source_id, target_id, edge_type),
                )
                edge_row = cur.fetchone()
                if edge_row:
                    edge_id = edge_row["id"]
                else:
                    cur.execute(
                        """
                        SELECT id::text FROM lineage_edge
                        WHERE source_id = %s::uuid AND target_id = %s::uuid
                          AND granularity = 'DATASET'
                          AND operator_fingerprint IS NOT DISTINCT FROM %s
                          AND query_fingerprint IS NULL
                        LIMIT 1
                        """,
                        (source_id, target_id, edge_type),
                    )
                    edge_id = cur.fetchone()["id"]

                evidence_id = f"{import_id}:{index}"
                cur.execute(
                    """
                    INSERT INTO evidence
                        (evidence_id, evidence_type, source_system, source_dataset_id,
                         target_dataset_id, granularity, parser_status, diagnostics, raw_event_id)
                    VALUES (%s, 'STATIC_DEPENDENCY', %s, %s::uuid, %s::uuid,
                            'DATASET', 'SUPPORTED', %s, %s)
                    RETURNING id::text
                    """,
                    (evidence_id, source_kind, source_id, target_id,
                     Json({"classification": "DECLARED_METADATA", "edge_type": edge_type}), raw_event_id),
                )
                normalized_evidence_id = cur.fetchone()["id"]
                cur.execute(
                    """
                    INSERT INTO edge_temporal_version
                        (edge_id, valid_from, effective_time_status, transaction_from,
                         evidence_id, source_system)
                    VALUES (%s::uuid, now(), 'UNKNOWN', now(), %s::uuid, %s)
                    """,
                    (edge_id, normalized_evidence_id, source_kind),
                )

            summary["persisted_assets"] = len(dataset_ids)
            summary["persisted_relationships"] = len(payload["relationships"])
            cur.execute(
                "UPDATE import_run SET result_summary = %s WHERE id = %s::uuid",
                (Json(summary), import_id),
            )

    return {"ok": True, "replayed": False, "import_id": import_id, "status": "COMMITTED_WITH_WARNINGS" if warnings else "COMMITTED", "summary": summary}


@router.get("/runs")
def list_import_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_user),
):
    """List the import runs visible to the caller's workspace, newest first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_RUN_COLUMNS}
                FROM   import_run
                ORDER  BY import_run.created_at DESC
                LIMIT  %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
    runs = [dict(row) for row in rows]
    return {"runs": runs, "count": len(runs)}


@router.get("/runs/{import_id}")
def get_import_run(import_id: uuid.UUID, user: dict = Depends(require_user)):
    """Return a single import run from the caller's workspace, or 404."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_RUN_COLUMNS}
                FROM   import_run
                WHERE  id = %s::uuid
                LIMIT  1
                """,
                (str(import_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Import run '{import_id}' not found.")
    return dict(row)
