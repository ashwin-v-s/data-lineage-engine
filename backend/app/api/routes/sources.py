"""Authenticated live PostgreSQL source-connection management.

A signed-in user registers a private, workspace-scoped connection to an external
PostgreSQL database, verifies that Kairos can read its schema, and syncs the
observed tables and columns into the catalog. The connection configuration
(including the password) is only ever persisted as the AES-256-GCM envelope
produced by :mod:`backend.app.services.token_crypto`; no route logs or returns
plaintext credentials or ciphertext.

Every database-touching endpoint first asserts that the reviewed
``source_connection`` migration is installed and fails closed with HTTP 503
otherwise, so the API stays honest before the migration is applied.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Literal

import psycopg2
from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.services.token_crypto import decrypt_token, encrypt_token
from ingestion.postgres_source import (
    SOURCE_KIND,
    PostgresSourceConfig,
    extract_postgres_source,
)

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_user)])

# Read-only projection of a source_connection row. UUIDs and timestamps are cast
# to text in SQL so the result is directly JSON-serialisable; the ciphertext is
# deliberately absent. Row-level security scopes rows to the caller's workspace,
# so no workspace_id is ever accepted from the client.
_SUMMARY_COLUMNS = """
    id::text                                                                    AS id,
    name                                                                        AS name,
    source_kind                                                                 AS source_kind,
    lifecycle_state                                                             AS lifecycle_state,
    to_char(last_checked_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS last_checked_at,
    last_error                                                                  AS last_error,
    to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')      AS created_at
"""


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    source_kind: Literal["postgresql"] = "postgresql"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    dbname: str = Field(min_length=1, max_length=128)
    user: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)
    schema_name: str = Field(default="public", min_length=1, max_length=128)


class SourceSummary(BaseModel):
    id: str
    name: str
    source_kind: str
    lifecycle_state: str
    last_checked_at: str | None = None
    last_error: str | None = None
    created_at: str | None = None


class TestResult(BaseModel):
    ok: bool
    lifecycle_state: str
    message: str
    table_count: int | None = None


class PreviewResult(BaseModel):
    ok: bool
    preview: dict
    commit_ready: bool
    commit_blocker: str | None = None


def _require_table(cur) -> None:
    """Fail closed (503) while the ``source_connection`` migration is missing."""
    cur.execute("SELECT to_regclass('public.source_connection') AS present")
    if not cur.fetchone()["present"]:
        raise HTTPException(
            status_code=503,
            detail=(
                "Source-connection storage is not installed. The reviewed "
                "source-connection migration must be applied first."
            ),
        )


def _load_config(cur, source_id: uuid.UUID) -> PostgresSourceConfig:
    """Decrypt the stored connection config for one source, or raise 404."""
    cur.execute(
        "SELECT config_ciphertext FROM source_connection WHERE id = %s::uuid",
        (str(source_id),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
    try:
        config = json.loads(decrypt_token(row["config_ciphertext"]))
        return PostgresSourceConfig(
            host=config["host"],
            port=int(config["port"]),
            dbname=config["dbname"],
            user=config["user"],
            password=config["password"],
            schema=config.get("schema", "public"),
        )
    except (ValueError, TypeError, KeyError, RuntimeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="The stored source configuration could not be read.",
        ) from exc


def _insert_asset(cur, asset: dict[str, Any], source_kind: str, source_ref: str) -> str:
    """Upsert one asset and its columns into dataset/column_record.

    Identical identity tuple and upsert to the static-ingest path: the source
    ref participates in the identity so same-named tables from separate
    databases do not overwrite each other.
    """
    namespace = str(asset.get("namespace") or "general")
    name = str(asset.get("name") or asset["qualified_name"].rsplit("/", 1)[-1])
    asset_type = str(asset.get("type") or asset.get("asset_type") or "table").upper()
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


def _summary(payload: dict[str, Any], warnings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "contract_version": payload["contract_version"],
        "assets": len(payload["assets"]),
        "columns": sum(len(a.get("metadata", {}).get("columns", [])) for a in payload["assets"]),
        "warnings": warnings,
        "provenance": payload["provenance"],
    }


@router.post("", response_model=SourceSummary)
def create_source(payload: SourceCreate, user: dict = Depends(require_user)):
    """Register an encrypted, workspace-scoped PostgreSQL connection."""
    config = {
        "host": payload.host,
        "port": payload.port,
        "dbname": payload.dbname,
        "user": payload.user,
        "password": payload.password,
        "schema": payload.schema_name,
    }
    ciphertext = encrypt_token(json.dumps(config))
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            try:
                cur.execute(
                    f"""
                    INSERT INTO source_connection
                        (name, source_kind, config_ciphertext, config_key_version,
                         lifecycle_state, created_by)
                    VALUES (%s, %s, %s, %s, 'CONFIGURED', %s::uuid)
                    RETURNING {_SUMMARY_COLUMNS}
                    """,
                    (payload.name, SOURCE_KIND, ciphertext, 1, user["id"]),
                )
            except psycopg2.errors.UniqueViolation as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"A source named '{payload.name}' already exists in this workspace.",
                ) from exc
            row = cur.fetchone()
    return dict(row)


@router.get("", response_model=list[SourceSummary])
def list_sources(user: dict = Depends(require_user)):
    """List the caller's workspace sources, newest first (never ciphertext)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute(
                f"""
                SELECT {_SUMMARY_COLUMNS}
                FROM   source_connection
                ORDER  BY created_at DESC, id DESC
                """
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/{source_id}", response_model=SourceSummary)
def get_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Return one source in the caller's workspace, or 404."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute(
                f"SELECT {_SUMMARY_COLUMNS} FROM source_connection WHERE id = %s::uuid",
                (str(source_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
    return dict(row)


@router.post("/{source_id}/test", response_model=TestResult)
def test_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Read the source schema and record the connector lifecycle state."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            config = _load_config(cur, source_id)
    result = extract_postgres_source(config)
    if result.ok:
        assert result.payload is not None
        state = "VERIFIED"
        message = "Connection verified; the source schema was read successfully."
        table_count: int | None = len(result.payload["assets"])
        last_error = None
    else:
        diagnostic = result.diagnostics[0] if result.diagnostics else None
        message = diagnostic.message if diagnostic else "The source could not be read."
        state, table_count, last_error = "ERROR", None, message
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source_connection
                SET lifecycle_state = %s, last_checked_at = now(),
                    updated_at = now(), last_error = %s
                WHERE id = %s::uuid
                """,
                (state, last_error, str(source_id)),
            )
    return TestResult(ok=bool(result.ok), lifecycle_state=state, message=message, table_count=table_count)


@router.post("/{source_id}/preview", response_model=PreviewResult)
def preview_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Read the source and summarise what a sync would persist, without writing."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            config = _load_config(cur, source_id)
    result = extract_postgres_source(config)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("SELECT to_regclass('public.import_run') AS present")
            run_table_present = bool(cur.fetchone()["present"])

    payload = result.payload
    warnings = [warning.as_dict() for warning in result.warnings]
    if payload is not None:
        preview = _summary(payload, warnings)
    else:
        preview = {
            "contract_version": None,
            "assets": 0,
            "columns": 0,
            "warnings": warnings,
            "provenance": None,
        }

    if not result.ok:
        blocker = (
            result.diagnostics[0].message
            if result.diagnostics
            else "The source did not produce a valid metadata payload."
        )
    elif not run_table_present:
        blocker = "The import-run migration is not installed in this Supabase project."
    else:
        blocker = None
    return PreviewResult(
        ok=bool(result.ok),
        preview=preview,
        commit_ready=bool(result.ok and run_table_present),
        commit_blocker=blocker,
    )


@router.post("/{source_id}/sync")
def sync_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Read the source and atomically persist its assets and provenance."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            config = _load_config(cur, source_id)
    result = extract_postgres_source(config)
    if not result.ok or result.payload is None:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Source sync failed",
                "diagnostics": [d.as_dict() for d in result.diagnostics],
            },
        )

    payload = result.payload
    content_hash = payload["provenance"]["content_sha256"]
    source_ref = payload["source"].get("ref") or config.redacted_ref
    idempotency_key = f"source:{content_hash}"
    summary = _summary(payload, [w.as_dict() for w in result.warnings])

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("SELECT to_regclass('public.import_run') AS present")
            if not cur.fetchone()["present"]:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Ingestion storage is not installed. The reviewed "
                        "import-run migration must be applied first."
                    ),
                )

            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended("
                "current_setting('kairos.workspace_id', true) || ':' || %s, 0))",
                (idempotency_key,),
            )
            cur.execute(
                "SELECT id::text, content_sha256 FROM import_run WHERE idempotency_key = %s LIMIT 1",
                (idempotency_key,),
            )
            existing = cur.fetchone()
            if existing:
                if existing["content_sha256"] != content_hash:
                    raise HTTPException(
                        status_code=409,
                        detail="This idempotency key was already used for different content.",
                    )
                cur.execute(
                    """
                    UPDATE source_connection
                    SET lifecycle_state = 'VERIFIED', last_checked_at = now(),
                        updated_at = now(), last_error = NULL
                    WHERE id = %s::uuid
                    """,
                    (str(source_id),),
                )
                return {
                    "ok": True,
                    "replayed": True,
                    "import_id": existing["id"],
                    "summary": summary,
                }

            cur.execute(
                """
                INSERT INTO import_run
                    (actor_user_id, idempotency_key, source_kind, source_ref,
                     content_sha256, contract_version, adapter_name, adapter_version,
                     status, result_summary)
                VALUES (%s::uuid, %s, 'database', %s, %s, %s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (
                    user["id"], idempotency_key, source_ref, content_hash,
                    payload["contract_version"], payload["provenance"]["adapter"],
                    payload["provenance"]["adapter_version"],
                    "COMMITTED_WITH_WARNINGS" if result.warnings else "COMMITTED",
                    Json(summary),
                ),
            )
            import_id = cur.fetchone()["id"]

            dataset_ids: dict[str, str] = {}
            for asset in payload["assets"]:
                dataset_ids[asset["id"]] = _insert_asset(cur, asset, "database", source_ref)

            summary["persisted_assets"] = len(dataset_ids)
            summary["persisted_relationships"] = 0
            cur.execute(
                "UPDATE import_run SET result_summary = %s WHERE id = %s::uuid",
                (Json(summary), import_id),
            )
            cur.execute(
                """
                UPDATE source_connection
                SET lifecycle_state = 'VERIFIED', last_checked_at = now(),
                    updated_at = now(), last_error = NULL
                WHERE id = %s::uuid
                """,
                (str(source_id),),
            )
    return {"ok": True, "replayed": False, "import_id": import_id, "summary": summary}


@router.delete("/{source_id}")
def delete_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Soft-revoke a source (lifecycle_state -> REVOKED); 404 when unknown."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute(
                """
                UPDATE source_connection
                SET lifecycle_state = 'REVOKED', updated_at = now()
                WHERE id = %s::uuid
                RETURNING id::text
                """,
                (str(source_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
    return {"ok": True, "id": row["id"], "lifecycle_state": "REVOKED"}
