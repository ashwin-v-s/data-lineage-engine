"""Authenticated live PostgreSQL source-connection management.

A signed-in user registers a private, workspace-scoped connection to an external
PostgreSQL database, verifies credentials, discovers the schema, and syncs the
observed tables and columns into the catalog. The connection configuration
(including the password) is only ever persisted as the AES-256-GCM envelope
produced by :mod:`backend.app.services.token_crypto`; no route logs or returns
plaintext credentials or ciphertext.

Lifecycle contract (Architecture v2 §5.4)
─────────────────────────────────────────
  POST   /sources                       → CONFIGURED
  POST   /sources/{id}/test             → AUTHENTICATED | ERROR
                                          (credential+reachability only, never discovery)
  POST   /sources/{id}/discover         → DISCOVERY_COMPLETE | ERROR
                                          (full schema read; always a separate step)
  PATCH  /sources/{id}                  → update schedule / scope
  POST   /sources/{id}/sync             → VERIFIED | SYNC_FAILED
                                          (persist discovered assets)
  GET    /sources/{id}/runs             → sync history from sync_job
  GET    /sources/health                → 12-field workspace rollup
  DELETE /sources/{id}                  → REVOKED

Security contract (Architecture v2 §9.4)
────────────────────────────────────────
  Credentials are tested with a narrow reachability check only.  The connector
  role must not be a superuser and must not hold write grants.  An admin
  credential is explicitly rejected with CREDENTIAL_TOO_PRIVILEGED.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Literal

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query
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

_SUMMARY_COLUMNS = """
    id::text                                                                       AS id,
    name                                                                           AS name,
    source_kind                                                                    AS source_kind,
    lifecycle_state                                                                AS lifecycle_state,
    to_char(last_checked_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS last_checked_at,
    to_char(last_successful_sync_at AT TIME ZONE 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')                                      AS last_successful_sync_at,
    last_sync_duration_ms                                                          AS last_sync_duration_ms,
    last_error                                                                     AS last_error,
    last_assets_discovered                                                         AS last_assets_discovered,
    last_assets_created                                                            AS last_assets_created,
    last_assets_updated                                                            AS last_assets_updated,
    last_assets_unchanged                                                          AS last_assets_unchanged,
    source_snapshot_hash                                                           AS source_snapshot_hash,
    permission_gaps                                                                AS permission_gaps,
    sync_schedule                                                                  AS sync_schedule,
    to_char(next_sync_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')     AS next_sync_at,
    to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')       AS created_at
"""

_RUN_COLUMNS = """
    id::text                                                                        AS id,
    source_connection_id::text                                                      AS source_connection_id,
    sync_mode                                                                       AS sync_mode,
    status                                                                          AS status,
    to_char(started_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')        AS started_at,
    to_char(finished_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')       AS finished_at,
    duration_ms                                                                     AS duration_ms,
    assets_discovered                                                               AS assets_discovered,
    assets_created                                                                  AS assets_created,
    assets_updated                                                                  AS assets_updated,
    assets_unchanged                                                                AS assets_unchanged,
    assets_deleted                                                                  AS assets_deleted,
    assets_failed                                                                   AS assets_failed,
    error_message                                                                   AS error_message
"""


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

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


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sync_schedule: str | None = Field(default=None, max_length=100)
    schema_name: str | None = Field(default=None, min_length=1, max_length=128)


class SourceSummary(BaseModel):
    id: str
    name: str
    source_kind: str
    lifecycle_state: str
    last_checked_at: str | None = None
    last_successful_sync_at: str | None = None
    last_sync_duration_ms: int | None = None
    last_error: str | None = None
    last_assets_discovered: int | None = None
    last_assets_created: int | None = None
    last_assets_updated: int | None = None
    last_assets_unchanged: int | None = None
    source_snapshot_hash: str | None = None
    permission_gaps: list | None = None
    sync_schedule: str | None = None
    next_sync_at: str | None = None
    created_at: str | None = None


class TestResult(BaseModel):
    ok: bool
    lifecycle_state: str
    message: str
    # /test does NOT return table_count — that is /discover's job.


class DiscoverResult(BaseModel):
    ok: bool
    lifecycle_state: str
    assets: int
    columns: int
    permission_gaps: list[str]
    snapshot_hash: str | None = None
    warnings: list[dict] = Field(default_factory=list)
    message: str


class HealthRow(BaseModel):
    source_id: str
    name: str
    lifecycle_state: str
    last_checked_at: str | None = None
    last_successful_sync_at: str | None = None
    last_sync_duration_ms: int | None = None
    assets_discovered: int | None = None
    assets_created: int | None = None
    assets_updated: int | None = None
    assets_unchanged: int | None = None
    permission_gaps: list | None = None
    sync_schedule: str | None = None
    next_sync_at: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_table(cur, table: str = "source_connection") -> None:
    cur.execute("SELECT to_regclass(%s) AS present", (f"public.{table}",))
    if not cur.fetchone()["present"]:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Required table '{table}' is not installed. "
                "Apply the source-connection migration first."
            ),
        )


def _load_config(cur, source_id: uuid.UUID) -> PostgresSourceConfig:
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
    namespace = str(asset.get("namespace") or "general")
    name = str(asset.get("name") or asset["qualified_name"].rsplit("/", 1)[-1])
    asset_type = str(asset.get("type") or "table").upper()
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
    for column in asset.get("metadata", {}).get("columns", []):
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


def _check_credential_privilege(config: PostgresSourceConfig) -> tuple[bool, str, list[str]]:
    """
    Connect with the supplied credentials and verify the role is not too privileged.

    Returns (ok, message, permission_gaps).

    Rules (Architecture v2 §9.4):
      - Must NOT be a superuser.
      - Must NOT hold any write grants (INSERT/UPDATE/DELETE/TRUNCATE) on any
        table in the target schema.
      - Holding broad SELECT ON ALL TABLES is a warning, not a hard block, unless
        it was explicitly not granted (data preview requires opt-in scope).

    This is intentionally narrow — it checks privileges only, not schema shape.
    """
    try:
        conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.dbname,
            user=config.user,
            password=config.password,
            connect_timeout=10,
        )
    except Exception as exc:
        return False, f"Connection failed: {type(exc).__name__}", []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Reject superusers
            cur.execute("SELECT usesuper FROM pg_user WHERE usename = current_user")
            row = cur.fetchone()
            if row and row["usesuper"]:
                return (
                    False,
                    "CREDENTIAL_TOO_PRIVILEGED: The supplied role is a superuser. "
                    "Kairos requires a dedicated read-only role (kairos_reader). "
                    "Never use an admin credential for catalog ingestion.",
                    [],
                )

            # 2. Check for write grants on the target schema
            cur.execute(
                """
                SELECT privilege_type
                FROM information_schema.role_table_grants
                WHERE grantee = current_user
                  AND table_schema = %s
                  AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
                LIMIT 1
                """,
                (config.schema,),
            )
            write_row = cur.fetchone()
            if write_row:
                return (
                    False,
                    f"CREDENTIAL_TOO_PRIVILEGED: The supplied role holds {write_row['privilege_type']} "
                    f"on schema '{config.schema}'. Kairos requires a read-only role with no write grants.",
                    [],
                )

            # 3. Identify permission gaps (tables visible in information_schema but
            #    not SELECTable by this role).
            cur.execute(
                """
                SELECT t.table_name
                FROM information_schema.tables t
                WHERE t.table_schema = %s
                  AND t.table_type = 'BASE TABLE'
                  AND NOT has_table_privilege(current_user, t.table_schema || '.' || t.table_name, 'SELECT')
                ORDER BY t.table_name
                """,
                (config.schema,),
            )
            gaps = [
                f"{config.schema}.{r['table_name']}: no SELECT grant"
                for r in cur.fetchall()
            ]

    except psycopg2.Error as exc:
        return False, f"Privilege check failed: {type(exc).__name__}", []
    finally:
        conn.close()

    if gaps:
        return (
            True,
            f"Connected but partial authorization: {len(gaps)} table(s) are not SELECTable. "
            "Full sync will skip them. Grant SELECT or reduce the scope.",
            gaps,
        )
    return True, "Credential verified: read-only, no write grants, full schema access.", []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=SourceSummary)
def create_source(payload: SourceCreate, user: dict = Depends(require_user)):
    """Register an encrypted, workspace-scoped PostgreSQL connection.

    Stores credentials in encrypted form only. Does NOT test the connection —
    call /test after creation.
    """
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
    """List all workspace sources, newest first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute(
                f"SELECT {_SUMMARY_COLUMNS} FROM source_connection ORDER BY created_at DESC, id DESC"
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


@router.get("/health")
def sources_health(user: dict = Depends(require_user)):
    """Return the 12-field health rollup for all sources in the workspace.

    Fields (Architecture v2 §5.5 / handout A2):
      1. source_id / name
      2. lifecycle_state
      3. last_checked_at           (last credential/reachability test)
      4. last_successful_sync_at   (last VERIFIED sync)
      5. last_sync_duration_ms
      6. assets_discovered         (from last sync)
      7. assets_created
      8. assets_updated
      9. assets_unchanged
      10. permission_gaps          (tables not SELECTable)
      11. sync_schedule            (cron expression or null)
      12. next_sync_at
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute(
                f"""
                SELECT {_SUMMARY_COLUMNS}
                FROM source_connection
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()

    health = []
    for row in rows:
        r = dict(row)
        # Determine connection_status label for the UI
        state = r.get("lifecycle_state", "CONFIGURED")
        gaps = r.get("permission_gaps") or []
        if state == "REVOKED":
            connection_status = "Revoked"
        elif state == "ERROR":
            connection_status = "Error"
        elif state == "CREDENTIALS_EXPIRED":
            connection_status = "Credentials expired"
        elif gaps:
            connection_status = f"Connected but partial authorization ({len(gaps)} gap(s))"
        elif state in ("VERIFIED", "DISCOVERY_COMPLETE", "PERSISTED", "NORMALIZED"):
            connection_status = "Connected"
        elif state in ("AUTHENTICATED", "REACHABLE", "AUTHORIZED"):
            connection_status = "Credential verified"
        else:
            connection_status = "Not tested"

        health.append({
            "source_id": r["id"],
            "name": r["name"],
            "source_kind": r["source_kind"],
            "lifecycle_state": state,
            "connection_status": connection_status,
            "last_checked_at": r.get("last_checked_at"),
            "last_successful_sync_at": r.get("last_successful_sync_at"),
            "last_sync_duration_ms": r.get("last_sync_duration_ms"),
            "assets_discovered": r.get("last_assets_discovered"),
            "assets_created": r.get("last_assets_created"),
            "assets_updated": r.get("last_assets_updated"),
            "assets_unchanged": r.get("last_assets_unchanged"),
            "permission_gaps": gaps,
            "sync_schedule": r.get("sync_schedule"),
            "next_sync_at": r.get("next_sync_at"),
        })

    return {"sources": health, "count": len(health)}


@router.get("/{source_id}", response_model=SourceSummary)
def get_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Return one source, or 404."""
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


@router.get("/{source_id}/runs")
def list_source_runs(
    source_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_user),
):
    """Return the sync history for one source, newest first.

    Each row is one entry from the sync_job table (created by /sync).
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            _require_table(cur, "sync_job")
            # Verify the source exists (RLS scopes this to the workspace)
            cur.execute(
                "SELECT id FROM source_connection WHERE id = %s::uuid",
                (str(source_id),),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
            cur.execute(
                f"""
                SELECT {_RUN_COLUMNS}
                FROM sync_job
                WHERE source_connection_id = %s::uuid
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
                """,
                (str(source_id), limit, offset),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*)::int AS n FROM sync_job WHERE source_connection_id = %s::uuid",
                (str(source_id),),
            )
            total = cur.fetchone()["n"]

    return {"runs": [dict(r) for r in rows], "count": len(rows), "total": total}


@router.patch("/{source_id}", response_model=SourceSummary)
def patch_source(
    source_id: uuid.UUID,
    payload: SourcePatch,
    user: dict = Depends(require_user),
):
    """Update the sync schedule or schema scope for a source."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            sets = []
            vals: list[Any] = []
            if payload.sync_schedule is not None:
                sets.append("sync_schedule = %s")
                vals.append(payload.sync_schedule or None)
            # schema_name change requires re-encryption of config
            if payload.schema_name is not None:
                config = _load_config(cur, source_id)
                new_config = {
                    "host": config.host,
                    "port": config.port,
                    "dbname": config.dbname,
                    "user": config.user,
                    "password": config.password,
                    "schema": payload.schema_name,
                }
                sets.append("config_ciphertext = %s")
                vals.append(encrypt_token(json.dumps(new_config)))
                sets.append("lifecycle_state = 'CONFIGURED'")  # re-test after scope change
            if not sets:
                # Nothing to change — return current state
                cur.execute(
                    f"SELECT {_SUMMARY_COLUMNS} FROM source_connection WHERE id = %s::uuid",
                    (str(source_id),),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
                return dict(row)

            sets.append("updated_at = now()")
            vals.append(str(source_id))
            cur.execute(
                f"""
                UPDATE source_connection
                SET {', '.join(sets)}
                WHERE id = %s::uuid
                RETURNING {_SUMMARY_COLUMNS}
                """,
                vals,
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
    return dict(row)


@router.post("/{source_id}/test", response_model=TestResult)
def test_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Credential and reachability check only — does NOT read the schema.

    Verifies:
      1. The database is reachable.
      2. The role is not a superuser.
      3. The role holds no write grants on the target schema.

    On success: lifecycle → AUTHENTICATED.
    On failure: lifecycle → ERROR with the specific rejection reason.

    This is intentionally separate from /discover. A passing /test does NOT
    mean discovery will succeed.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            config = _load_config(cur, source_id)

    ok, message, gaps = _check_credential_privilege(config)

    new_state = "AUTHENTICATED" if ok else "ERROR"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source_connection
                SET lifecycle_state = %s,
                    last_checked_at = now(),
                    updated_at = now(),
                    last_error = %s,
                    permission_gaps = %s::jsonb
                WHERE id = %s::uuid
                """,
                (
                    new_state,
                    None if ok else message,
                    json.dumps(gaps),
                    str(source_id),
                ),
            )

    return TestResult(ok=ok, lifecycle_state=new_state, message=message)


@router.post("/{source_id}/discover", response_model=DiscoverResult)
def discover_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Read the full source schema and record counts for review.

    Does NOT write any assets to the catalog — that is /sync.
    Sets lifecycle → DISCOVERY_COMPLETE on success, ERROR on failure.

    This is the step between /test and /sync:
      /test  → credential check only
      /discover → schema read, count review  ← this endpoint
      /sync  → persist to catalog
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            config = _load_config(cur, source_id)

    result = extract_postgres_source(config)

    if not result.ok or result.payload is None:
        diagnostic = result.diagnostics[0] if result.diagnostics else None
        message = diagnostic.message if diagnostic else "Discovery failed."
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE source_connection
                    SET lifecycle_state = 'ERROR', last_error = %s,
                        last_checked_at = now(), updated_at = now()
                    WHERE id = %s::uuid
                    """,
                    (message, str(source_id)),
                )
        return DiscoverResult(
            ok=False,
            lifecycle_state="ERROR",
            assets=0,
            columns=0,
            permission_gaps=[],
            message=message,
        )

    payload = result.payload
    asset_count = len(payload["assets"])
    column_count = sum(len(a.get("metadata", {}).get("columns", [])) for a in payload["assets"])
    snapshot_hash = payload["provenance"].get("content_sha256")
    warnings = [w.as_dict() for w in result.warnings]

    # Detect permission gaps from warnings
    gaps: list[str] = []
    for w in result.warnings:
        if "permission" in (w.code or "").lower() or "select" in (w.message or "").lower():
            gaps.append(w.message)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source_connection
                SET lifecycle_state = 'DISCOVERY_COMPLETE',
                    last_checked_at = now(),
                    updated_at = now(),
                    last_error = NULL,
                    last_assets_discovered = %s,
                    source_snapshot_hash = %s,
                    permission_gaps = %s::jsonb
                WHERE id = %s::uuid
                """,
                (asset_count, snapshot_hash, json.dumps(gaps), str(source_id)),
            )

    return DiscoverResult(
        ok=True,
        lifecycle_state="DISCOVERY_COMPLETE",
        assets=asset_count,
        columns=column_count,
        permission_gaps=gaps,
        snapshot_hash=snapshot_hash,
        warnings=warnings,
        message=f"Discovery complete: {asset_count} asset(s), {column_count} column(s).",
    )


@router.post("/{source_id}/preview")
def preview_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Read the source and summarise what a sync would persist, without writing."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            config = _load_config(cur, source_id)

    result = extract_postgres_source(config)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.import_run') AS present")
            run_table_present = bool(cur.fetchone()["present"])

    payload = result.payload
    warnings = [w.as_dict() for w in result.warnings]
    preview = {
        "contract_version": payload["contract_version"] if payload else None,
        "assets": len(payload["assets"]) if payload else 0,
        "columns": sum(len(a.get("metadata", {}).get("columns", [])) for a in (payload["assets"] if payload else [])),
        "warnings": warnings,
        "provenance": payload["provenance"] if payload else None,
    }

    if not result.ok:
        blocker = result.diagnostics[0].message if result.diagnostics else "Source did not produce a valid payload."
    elif not run_table_present:
        blocker = "The import-run migration is not installed."
    else:
        blocker = None

    return {
        "ok": bool(result.ok),
        "preview": preview,
        "commit_ready": bool(result.ok and run_table_present),
        "commit_blocker": blocker,
    }


@router.post("/{source_id}/sync")
def sync_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Read the source and atomically persist assets into the catalog."""
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

    import time
    sync_start = time.monotonic()
    payload = result.payload
    content_hash = payload["provenance"]["content_sha256"]
    source_ref = payload["source"].get("ref") or config.redacted_ref
    idempotency_key = f"source:{content_hash}"
    warnings_list = [w.as_dict() for w in result.warnings]

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("SELECT to_regclass('public.import_run') AS present")
            if not cur.fetchone()["present"]:
                raise HTTPException(
                    status_code=503,
                    detail="Ingestion storage is not installed. Apply the import-run migration first.",
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
            asset_count = len(payload["assets"])

            if existing:
                if existing["content_sha256"] != content_hash:
                    raise HTTPException(status_code=409, detail="Idempotency key reused for different content.")
                cur.execute(
                    """
                    UPDATE source_connection
                    SET lifecycle_state = 'VERIFIED', last_checked_at = now(),
                        updated_at = now(), last_error = NULL,
                        last_successful_sync_at = now()
                    WHERE id = %s::uuid
                    """,
                    (str(source_id),),
                )
                return {"ok": True, "replayed": True, "import_id": existing["id"]}

            summary = {
                "contract_version": payload["contract_version"],
                "assets": asset_count,
                "columns": sum(len(a.get("metadata", {}).get("columns", [])) for a in payload["assets"]),
                "warnings": warnings_list,
                "provenance": payload["provenance"],
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
                    payload["contract_version"],
                    payload["provenance"]["adapter"],
                    payload["provenance"]["adapter_version"],
                    "COMMITTED_WITH_WARNINGS" if result.warnings else "COMMITTED",
                    Json(summary),
                ),
            )
            import_id = cur.fetchone()["id"]

            dataset_ids: dict[str, str] = {}
            for asset in payload["assets"]:
                dataset_ids[asset["id"]] = _insert_asset(cur, asset, "database", source_ref)

            duration_ms = int((time.monotonic() - sync_start) * 1000)
            summary["persisted_assets"] = len(dataset_ids)
            summary["persisted_relationships"] = 0
            cur.execute(
                "UPDATE import_run SET result_summary = %s WHERE id = %s::uuid",
                (Json(summary), import_id),
            )

            # Record sync_job row if the table exists
            cur.execute("SELECT to_regclass('public.sync_job') AS present")
            if cur.fetchone()["present"]:
                cur.execute(
                    """
                    INSERT INTO sync_job
                        (source_connection_id, sync_mode, status, finished_at,
                         assets_discovered, assets_created, snapshot_hash)
                    VALUES (%s::uuid, 'manual', 'completed', now(), %s, %s, %s)
                    """,
                    (str(source_id), len(dataset_ids), len(dataset_ids),
                     payload["provenance"].get("content_sha256")),
                )

            cur.execute(
                """
                UPDATE source_connection
                SET lifecycle_state = 'VERIFIED', last_checked_at = now(),
                    updated_at = now(), last_error = NULL,
                    last_successful_sync_at = now(),
                    last_sync_duration_ms = %s,
                    last_assets_discovered = %s,
                    last_assets_created = %s
                WHERE id = %s::uuid
                """,
                (duration_ms, len(dataset_ids), len(dataset_ids), str(source_id)),
            )

    return {"ok": True, "replayed": False, "import_id": import_id, "summary": summary}


@router.delete("/{source_id}")
def delete_source(source_id: uuid.UUID, user: dict = Depends(require_user)):
    """Soft-revoke a source; evidence is kept as history (§9.9)."""
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
