"""
OpenLineage runtime evidence ingestion.
──────────────────────────────────────
POST /api/v1/ingest/openlineage           validate + persist one event or a batch
POST /api/v1/ingest/openlineage/preview   validate + describe without writes

Both endpoints require an authenticated workspace: the persistence path writes
into workspace-scoped tables, so an unauthenticated producer cannot be given a
workspace implicitly. Two credentials are accepted:

  * a signed-in user session (`Authorization: Bearer <supabase token>`, or a
    Kairos API key), which carries its own workspace; and
  * the server-side ``KAIROS_OPENLINEAGE_WEBHOOK_SECRET`` bearer secret used by
    external schedulers, scoped to ``KAIROS_OPENLINEAGE_WORKSPACE_ID``.

External producers that cannot send a bearer token can instead sign the raw
body with ``KAIROS_WEBHOOK_SIGNING_SECRET`` and send
``X-Kairos-Signature: sha256=<hex-hmac-sha256>``. A signed request is scoped to
``KAIROS_OPENLINEAGE_WORKSPACE_ID`` exactly like the shared-secret path, and a
present-but-invalid signature is rejected instead of falling back to a session.

The secret paths exist only when the matching variables are configured;
otherwise the endpoint requires a normal user session.

Rules (from Architecture Pack §12 and handout G1/A1) live in
``backend/app/services/openlineage_ingest.py`` — this module only handles the
HTTP contract. In short:

  1. Every accepted event is stored immutably in raw_event, once.
  2. COMPLETE events produce RUNTIME_POSITIVE evidence (dataset granularity).
  3. Missing events, duplicates and non-COMPLETE events never create negative
     evidence. Absence is not stored.
  4. No cartesian edge: a dataset edge is created only when the event names
     exactly one output.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from typing import Any, AsyncGenerator, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

logger = logging.getLogger("kairos.api")
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.errors import api_error
from backend.app.auth import require_user
from backend.app.db import get_conn, reset_workspace_id, set_workspace_id
from backend.app.identity.canonical_ids import canonical_import_identity
from backend.app.services.openlineage_ingest import (
    MAX_BATCH_SIZE,
    ingest_openlineage_events,
    summarize_batch,
)
from ingestion.static_files import parse_static_file

router = APIRouter(prefix="/ingest", tags=["ingestion"])


async def _extract_events(request: Request):
    """Return ``(raw_events, error_response)`` from an OpenLineage body."""
    try:
        body = await request.json()
    except Exception:
        return None, api_error(request, "Request body must be valid JSON", 400, "INVALID_JSON")
    if not isinstance(body, dict):
        return None, api_error(request, "Request body must be a JSON object", 400, "INVALID_PAYLOAD")

    if isinstance(body.get("events"), list):
        raw_events = body["events"]
    elif "eventType" in body:
        raw_events = [body]
    else:
        return None, api_error(
            request,
            'Provide either a single OpenLineage event object or {"events": [...]}',
            400,
            "INVALID_PAYLOAD",
        )
    if len(raw_events) > MAX_BATCH_SIZE:
        return None, api_error(
            request,
            f"Batch size exceeds limit of {MAX_BATCH_SIZE} events per request",
            413,
            "BATCH_TOO_LARGE",
        )
    return raw_events, None


def _webhook_principal() -> dict | None:
    """Return the configured secret-authenticated principal, if usable."""
    expected = (os.getenv("KAIROS_OPENLINEAGE_WEBHOOK_SECRET") or "").strip()
    workspace = (os.getenv("KAIROS_OPENLINEAGE_WORKSPACE_ID") or "").strip()
    if not expected or not workspace:
        return None
    try:
        workspace = str(uuid.UUID(workspace))
    except (ValueError, AttributeError):
        return None
    return {"id": None, "workspace_id": workspace, "auth": "openlineage_webhook"}


SIGNATURE_HEADER = "x-kairos-signature"
SIGNING_SECRET_ENV = "KAIROS_WEBHOOK_SIGNING_SECRET"


def _signature_secret() -> str:
    return (os.getenv(SIGNING_SECRET_ENV) or "").strip()


def _normalise_signature(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    if raw.startswith("sha256="):
        raw = raw.split("=", 1)[1].strip()
    return raw


def _signature_principal() -> Optional[dict]:
    """Workspace a signature-verified producer may write to.

    A signed request is authorised by its own secret, so it does not need the
    shared bearer secret to be configured. It still needs exactly one workspace
    to write into; without that the server cannot scope the write safely.
    """
    workspace = (os.getenv("KAIROS_OPENLINEAGE_WORKSPACE_ID") or "").strip()
    if not workspace:
        return None
    try:
        workspace = str(uuid.UUID(workspace))
    except (ValueError, AttributeError):
        return None
    return {"id": None, "workspace_id": workspace, "auth": "openlineage_signature"}


async def _signature_state(request: Request) -> Optional[tuple[bool, str]]:
    """Verify an ``X-Kairos-Signature`` HMAC when the caller sends one.

    Returns ``None`` when the header is absent, so session and shared-secret
    callers are unaffected. Returns ``(ok, reason)`` otherwise; the reason is a
    short diagnostic that never includes the secret or the expected digest.
    """
    header = request.headers.get(SIGNATURE_HEADER)
    if header is None or not header.strip():
        return None
    secret = _signature_secret()
    if not secret:
        return False, "Webhook signature verification is not configured on this server"
    body = await request.body()
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = _normalise_signature(header)
    if not provided or not secrets.compare_digest(provided, expected):
        return False, "Webhook signature does not match the request body"
    return True, ""


async def openlineage_producer(request: Request) -> AsyncGenerator[dict, None]:
    """Authorize an OpenLineage producer via signature, webhook secret or session.

    The secret is compared in constant time and only accepted when the server
    has both a secret and the single workspace it may write to. A signed-in
    session is validated by the standard ``require_user`` dependency, so API
    keys and Supabase tokens keep working unchanged. A request that carries an
    ``X-Kairos-Signature`` header must carry a valid one: an invalid signature
    never falls through to an ambient session.
    """
    signature = await _signature_state(request)
    if signature is not None:
        ok, reason = signature
        if not ok:
            raise HTTPException(status_code=401, detail=reason)
        signed_principal = _signature_principal()
        if signed_principal is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "A verified webhook signature needs "
                    "KAIROS_OPENLINEAGE_WORKSPACE_ID to scope the write"
                ),
            )
        token = set_workspace_id(signed_principal["workspace_id"])
        try:
            yield {**signed_principal, "auth": "openlineage_signature"}
        finally:
            reset_workspace_id(token)
        return

    authorization = request.headers.get("authorization", "")
    supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    principal = _webhook_principal()
    expected = (os.getenv("KAIROS_OPENLINEAGE_WEBHOOK_SECRET") or "").strip()
    if principal and supplied and secrets.compare_digest(supplied, expected):
        token = set_workspace_id(principal["workspace_id"])
        try:
            yield principal
        finally:
            reset_workspace_id(token)
        return

    credentials = (
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=supplied)
        if supplied
        else None
    )
    async for user in require_user(request, credentials):
        yield user


@router.post(
    "/openlineage/preview",
    summary="Validate and preview OpenLineage events without writing",
    description=(
        "Returns the normalized producer, event type, event time, job, run id and "
        "input/output datasets with validation warnings. No database writes."
    ),
)
async def preview_openlineage(request: Request, producer: dict = Depends(openlineage_producer)):
    raw_events, error = await _extract_events(request)
    if error is not None:
        return error
    summary = summarize_batch(raw_events)
    summary["ok"] = True
    summary["writes"] = 0
    return summary


@router.post(
    "/openlineage",
    summary="Ingest one or more OpenLineage runtime events",
    description=(
        "Stores events immutably, records the job and run, and normalizes "
        "COMPLETE events into RUNTIME_POSITIVE dataset evidence plus an observed "
        "lineage relationship. Non-COMPLETE events do not produce evidence."
    ),
)
async def ingest_openlineage(request: Request, producer: dict = Depends(openlineage_producer)) -> JSONResponse:
    raw_events, error = await _extract_events(request)
    if error is not None:
        return error
    if not raw_events:
        return JSONResponse(
            status_code=200,
            content={
                "accepted": 0, "duplicate": 0, "skipped": 0,
                "evidence_created": 0, "edges_created": 0, "runs_written": 0,
                "diagnostics": ["Empty event batch."],
            },
        )
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                result = ingest_openlineage_events(cur, raw_events)
    except Exception:
        # The driver message can carry host, user or table detail. Log it with the
        # request id and give the caller a stable message instead.
        logger.exception(
            "OpenLineage ingest storage failure request_id=%s",
            getattr(request.state, "request_id", None),
        )
        return api_error(
            request,
            "Ingestion storage is temporarily unavailable. Retry, or share the request ID with support.",
            503,
            "STORAGE_UNAVAILABLE",
        )
    return JSONResponse(status_code=200, content=result)


# Authenticated preview and explicit commit for static metadata imports.
_RUN_COLUMNS = """
    id::text AS id,
    source_kind,
    source_ref,
    content_sha256,
    contract_version,
    adapter_name,
    adapter_version,
    status,
    result_summary,
    to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS created_at
"""


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["metadata_graph", "sql_file", "dbt_manifest", "dbt_run_results",
                   "postgres_query_log", "file_inventory", "csv_headers"]
    filename: str = Field(default="upload", min_length=1, max_length=255)
    content: Any
    source_revision: str | None = Field(default=None, max_length=512)


class CommitInput(ImportInput):
    idempotency_key: str = Field(min_length=1, max_length=256)


def _resolve_kind(kind: str, content: Any) -> str:
    """Accept a file inventory that a client labelled as a metadata graph.

    Clients detect the format from the file itself at the calling site, so an
    inventory document that also carries ``contract_version`` can be submitted
    as ``metadata_graph``.  When the payload has a ``files`` array and no
    ``assets`` array only the inventory adapter can read it, so use that rather
    than rejecting the import with ASSETS_REQUIRED.
    """
    if kind != "metadata_graph":
        return kind
    data: Any = content
    if isinstance(data, (bytes, bytearray, str)):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return kind
    if (
        isinstance(data, dict)
        and isinstance(data.get("files"), list)
        and not isinstance(data.get("assets"), list)
    ):
        return "file_inventory"
    return kind


def _parse(request: ImportInput):
    result = parse_static_file(
        _resolve_kind(request.kind, request.content), request.content, filename=request.filename,
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
    """Validate and normalize an import without database writes."""
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


def _ensure_column(cur, dataset_id: str, column_name: str) -> str:
    """Return the column_record id, creating the column when absent."""
    cur.execute(
        """
        INSERT INTO column_record (dataset_id, schema_version, column_name)
        VALUES (%s::uuid, 'v1', %s)
        ON CONFLICT (dataset_id, schema_version, column_name) DO NOTHING
        RETURNING id::text AS id
        """,
        (dataset_id, column_name),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        """
        SELECT id::text AS id FROM column_record
        WHERE dataset_id = %s::uuid AND schema_version = 'v1' AND column_name = %s
        LIMIT 1
        """,
        (dataset_id, column_name),
    )
    return cur.fetchone()["id"]


def _insert_asset(cur, asset: dict[str, Any], source_kind: str, source_ref: str) -> str:
    namespace = str(asset.get("namespace") or "general")
    name = str(asset.get("name") or asset["qualified_name"].rsplit("/", 1)[-1])
    database_name, schema_name, asset_type = canonical_import_identity(asset)
    cur.execute(
        """
        SELECT public.kairos_upsert_dataset(%s, %s, %s, %s, %s, %s)::text AS id
        """,
        (source_kind, namespace, database_name, schema_name, name, asset_type),
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
    """Revalidate and atomically persist assets, declared edges, and provenance."""
    return _commit_import(request, user, source_kind="upload")


def _commit_import(
    request: CommitInput,
    user: dict,
    *,
    source_kind: Literal["upload", "github"] = "upload",
    trusted_source_ref: str | None = None,
):
    """Shared persistence implementation; non-upload origins are server-verified."""
    payload, warnings = _parse(request)
    content_hash = payload["provenance"]["content_sha256"]
    source_ref = trusted_source_ref or payload["source"].get("ref") or payload["provenance"].get("original_filename") or ""
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
                "SELECT id::text, content_sha256, result_summary, status FROM import_run WHERE idempotency_key = %s LIMIT 1",
                (request.idempotency_key,),
            )
            existing = cur.fetchone()
            if existing:
                if existing["content_sha256"] != content_hash:
                    raise HTTPException(status_code=409, detail="This idempotency key was already used for different content.")
                return {
                    "ok": True, "replayed": True, "import_id": existing["id"],
                    "status": existing["status"], "summary": existing["result_summary"],
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
                "INSERT INTO raw_event (event_id, payload, payload_hash, source_system) VALUES (%s, %s, %s, %s)",
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

                # A static projection carries a column pair; persist it as a
                # COLUMN edge so /column-lineage reads real stored evidence.
                source_column = relationship.get("source_column")
                target_column = relationship.get("target_column")
                if not source_column or not target_column:
                    continue
                source_column_id = _ensure_column(cur, source_id, str(source_column))
                target_column_id = _ensure_column(cur, target_id, str(target_column))
                cur.execute(
                    """
                    INSERT INTO lineage_edge
                        (source_id, target_id, granularity, operator_fingerprint)
                    VALUES (%s::uuid, %s::uuid, 'COLUMN', %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id::text
                    """,
                    (source_column_id, target_column_id, edge_type),
                )
                column_edge = cur.fetchone()
                if column_edge:
                    column_edge_id = column_edge["id"]
                else:
                    cur.execute(
                        """
                        SELECT id::text FROM lineage_edge
                        WHERE source_id = %s::uuid AND target_id = %s::uuid
                          AND granularity = 'COLUMN'
                          AND operator_fingerprint IS NOT DISTINCT FROM %s
                          AND query_fingerprint IS NULL
                        LIMIT 1
                        """,
                        (source_column_id, target_column_id, edge_type),
                    )
                    column_edge_id = cur.fetchone()["id"]

                column_evidence_id = f"{import_id}:col:{index}"
                cur.execute(
                    """
                    INSERT INTO evidence
                        (evidence_id, evidence_type, source_system, source_dataset_id,
                         target_dataset_id, source_column_id, target_column_id,
                         granularity, operator, parser_status, diagnostics, raw_event_id)
                    VALUES (%s, 'STATIC_DEPENDENCY', %s, %s::uuid, %s::uuid,
                            %s::uuid, %s::uuid, 'COLUMN', %s, 'SUPPORTED', %s, %s)
                    RETURNING id::text
                    """,
                    (
                        column_evidence_id, source_kind, source_id, target_id,
                        source_column_id, target_column_id, edge_type,
                        Json({
                            "classification": "DECLARED_METADATA",
                            "source_column": str(source_column),
                            "target_column": str(target_column),
                        }),
                        raw_event_id,
                    ),
                )
                column_evidence_row = cur.fetchone()["id"]
                cur.execute(
                    """
                    INSERT INTO edge_temporal_version
                        (edge_id, valid_from, effective_time_status, transaction_from,
                         evidence_id, source_system)
                    VALUES (%s::uuid, now(), 'UNKNOWN', now(), %s::uuid, %s)
                    """,
                    (column_edge_id, column_evidence_row, source_kind),
                )

            summary["persisted_assets"] = len(dataset_ids)
            summary["persisted_relationships"] = len(payload["relationships"])
            cur.execute("UPDATE import_run SET result_summary = %s WHERE id = %s::uuid", (Json(summary), import_id))

    return {
        "ok": True,
        "replayed": False,
        "import_id": import_id,
        "status": "COMMITTED_WITH_WARNINGS" if warnings else "COMMITTED",
        "summary": summary,
    }


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
                f"SELECT {_RUN_COLUMNS} FROM import_run ORDER BY import_run.created_at DESC LIMIT %s OFFSET %s",
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
                f"SELECT {_RUN_COLUMNS} FROM import_run WHERE id = %s::uuid LIMIT 1",
                (str(import_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Import run '{import_id}' not found.")
    return dict(row)
