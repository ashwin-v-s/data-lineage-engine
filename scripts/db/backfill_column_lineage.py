"""Backfill column-level lineage for an already-imported SQL file.

BUG-03: static SQL imports recorded only dataset edges, so
``GET /api/v1/column-lineage`` returned ``total: 0`` even though the SQL
projection names source and target columns.  The SQLGlot adapter now emits
column pairs; this script replays the stored raw SQL of the newest SQL import
into the workspace, so an existing catalog gets the same evidence without
requiring a second upload.

The script is idempotent: every written row has a deterministic identifier and
is skipped when it already exists.  It never invents a mapping: only explicit
``SELECT`` projection columns are used.

Usage
-----
    python scripts/db/backfill_column_lineage.py --workspace <uuid>
    python scripts/db/backfill_column_lineage.py --workspace <uuid> --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.identity.canonical_ids import (  # noqa: E402
    asset_identity_kind,
    canonical_import_identity,
)
from ingestion.sql.static_file import parse_sql_file  # noqa: E402


def _identity_kind(asset_type: str) -> str:
    return asset_identity_kind(asset_type)


def _resolve_dataset(cur, workspace_id: str, asset: dict) -> str | None:
    database_name, schema_name, asset_type = canonical_import_identity(asset)
    cur.execute(
        """
        SELECT id::text AS id FROM dataset
        WHERE workspace_id = %s
          AND schema_key = lower(%s)
          AND name_key = lower(%s)
          AND identity_kind = %s
        LIMIT 1
        """,
        (workspace_id, schema_name, asset["name"], _identity_kind(asset_type)),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "SELECT public.kairos_upsert_dataset(%s, %s, %s, %s, %s, %s)::text AS id",
        (
            "upload",
            str(asset.get("namespace") or "general"),
            database_name,
            schema_name,
            asset["name"],
            asset_type,
        ),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _ensure_column(cur, dataset_id: str, column_name: str) -> str:
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Workspace UUID to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing")
    args = parser.parse_args(argv)

    load_dotenv(dotenv_path=str(ROOT / ".env"))
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    inserted = 0
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (args.workspace,))
            cur.execute(
                """
                SELECT ir.id::text AS id, re.payload AS payload
                FROM import_run AS ir
                JOIN raw_event AS re ON re.event_id = 'kairos-import:' || ir.id::text
                WHERE ir.workspace_id = %s
                  AND ir.adapter_name = 'kairos.sqlglot_file'
                ORDER BY ir.created_at DESC
                LIMIT 1
                """,
                (args.workspace,),
            )
            run = cur.fetchone()
            if run is None:
                print("No SQL-file import exists for this workspace; nothing to backfill.")
                conn.rollback()
                return 1

            payload = run["payload"] or {}
            assets = payload.get("assets") or []
            sql = ""
            if assets and isinstance(assets[0], dict):
                sql = (assets[0].get("metadata") or {}).get("original_sql") or ""
            if not sql:
                print("The stored SQL import has no original SQL text to replay.")
                conn.rollback()
                return 1

            filename = (payload.get("source") or {}).get("ref") or "backfill.sql"
            parsed = parse_sql_file(sql, filename=filename)
            if not parsed.ok or parsed.payload is None:
                print("SQL could not be parsed:", [d.as_dict() for d in parsed.diagnostics], file=sys.stderr)
                conn.rollback()
                return 1

            dataset_ids: dict[str, str] = {}
            for asset in parsed.payload["assets"]:
                # The adapter also emits the SQL file itself as a FILE asset;
                # only data assets can own columns or lineage anchors.
                if _identity_kind(asset.get("type")) != "DATASET":
                    continue
                dataset_id = _resolve_dataset(cur, args.workspace, asset)
                if dataset_id is None:
                    continue
                dataset_ids[asset["id"]] = dataset_id
                for column in (asset.get("metadata") or {}).get("columns", []):
                    if isinstance(column, dict) and isinstance(column.get("name"), str):
                        _ensure_column(cur, dataset_id, column["name"])

            run_key = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
            for index, relationship in enumerate(parsed.payload["relationships"]):
                source_column = relationship.get("source_column")
                target_column = relationship.get("target_column")
                source_dataset = dataset_ids.get(relationship["source_id"])
                target_dataset = dataset_ids.get(relationship["target_id"])
                if not (source_column and target_column and source_dataset and target_dataset):
                    continue
                evidence_key = f"column-backfill:{run_key}:{index}"
                cur.execute(
                    "SELECT 1 FROM evidence WHERE workspace_id = %s AND evidence_id = %s",
                    (args.workspace, evidence_key),
                )
                if cur.fetchone():
                    continue

                source_column_id = _ensure_column(cur, source_dataset, source_column)
                target_column_id = _ensure_column(cur, target_dataset, target_column)
                edge_type = relationship.get("edge_type") or "sql_column_candidate"

                cur.execute(
                    """
                    INSERT INTO lineage_edge (source_id, target_id, granularity, operator_fingerprint)
                    VALUES (%s::uuid, %s::uuid, 'COLUMN', %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id::text AS id
                    """,
                    (source_column_id, target_column_id, edge_type),
                )
                edge = cur.fetchone()
                if edge:
                    edge_id = edge["id"]
                else:
                    cur.execute(
                        """
                        SELECT id::text AS id FROM lineage_edge
                        WHERE source_id = %s::uuid AND target_id = %s::uuid
                          AND granularity = 'COLUMN'
                          AND operator_fingerprint = %s
                          AND query_fingerprint IS NULL
                        LIMIT 1
                        """,
                        (source_column_id, target_column_id, edge_type),
                    )
                    edge_id = cur.fetchone()["id"]

                cur.execute(
                    """
                    INSERT INTO evidence
                        (evidence_id, evidence_type, source_system, source_dataset_id,
                         target_dataset_id, source_column_id, target_column_id, granularity,
                         operator, parser_status, diagnostics, raw_event_id)
                    VALUES (%s, 'STATIC_DEPENDENCY', 'upload', %s::uuid, %s::uuid,
                            %s::uuid, %s::uuid, 'COLUMN', %s, 'SUPPORTED', %s, %s)
                    RETURNING id::text AS id
                    """,
                    (
                        evidence_key, source_dataset, target_dataset,
                        source_column_id, target_column_id, edge_type,
                        Json({
                            "classification": "DECLARED_METADATA",
                            "source_column": source_column,
                            "target_column": target_column,
                            "provenance": relationship.get("provenance"),
                            "backfill": "scripts/db/backfill_column_lineage.py",
                        }),
                        "kairos-import:" + run["id"],
                    ),
                )
                evidence_id = cur.fetchone()["id"]
                cur.execute(
                    """
                    INSERT INTO edge_temporal_version
                        (edge_id, valid_from, effective_time_status, transaction_from,
                         evidence_id, source_system)
                    VALUES (%s::uuid, now(), 'UNKNOWN', now(), %s::uuid, 'upload')
                    """,
                    (edge_id, evidence_id),
                )
                inserted += 1

            if args.dry_run:
                conn.rollback()
                print(f"DRY RUN: would insert {inserted} column mappings.")
                return 0
            conn.commit()
            print(
                f"Backfilled {inserted} column mappings into workspace {args.workspace} "
                f"from import {run['id']}."
            )
            return 0
    except Exception as exc:
        conn.rollback()
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
