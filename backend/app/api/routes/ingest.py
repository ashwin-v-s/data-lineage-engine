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
