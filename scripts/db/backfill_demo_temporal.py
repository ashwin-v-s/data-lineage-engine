"""Give the existing demo dbt evidence its source-declared valid time.

The dbt manifest declares ``metadata.generated_at``.  Imports made before the
adapter forwarded that timestamp stored every dependency as
``effective_time_status='UNKNOWN'``, so the Time travel page returned no dated
records even though the source provided a real timestamp.

This script updates only the evidence belonging to the newest dbt manifest
import in one workspace.  It never invents a timestamp: the value is read from
the manifest file, and only rows currently marked UNKNOWN are changed.

Usage
-----
    python scripts/db/backfill_demo_temporal.py --workspace <uuid>
    python scripts/db/backfill_demo_temporal.py --workspace <uuid> --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "demo-authenticated-ingestion" / "dbt_production_manifest.json"


def _generated_at(path: Path) -> datetime:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    raw = (document.get("metadata") or {}).get("generated_at")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Manifest has no metadata.generated_at")
    value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Workspace UUID to repair")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="dbt manifest that supplied the import (default: demo fixture)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args(argv)

    try:
        valid_from = _generated_at(Path(args.manifest))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    load_dotenv(dotenv_path=str(ROOT / ".env"))
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (args.workspace,))
            cur.execute(
                """
                SELECT id::text AS id
                FROM import_run
                WHERE workspace_id = %s AND adapter_name = 'kairos.dbt_manifest'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (args.workspace,),
            )
            run = cur.fetchone()
            if run is None:
                print("No dbt manifest import exists for this workspace; nothing to repair.")
                conn.rollback()
                return 1
            raw_event_id = "kairos-import:" + run["id"]

            cur.execute(
                """
                SELECT count(*)::int AS n
                FROM edge_temporal_version etv
                JOIN evidence e ON e.id = etv.evidence_id
                WHERE e.raw_event_id = %s
                  AND etv.effective_time_status = 'UNKNOWN'
                """,
                (raw_event_id,),
            )
            pending = int(cur.fetchone()["n"])
            print(
                f"Import {run['id']}: {pending} undated temporal version(s); "
                f"source valid time {valid_from.isoformat()}."
            )
            if args.dry_run:
                conn.rollback()
                print(f"DRY RUN: would date {pending} record(s).")
                return 0

            cur.execute(
                """
                UPDATE edge_temporal_version etv
                   SET valid_from = %s,
                       effective_time_status = 'KNOWN'
                  FROM evidence e
                 WHERE e.id = etv.evidence_id
                   AND e.raw_event_id = %s
                   AND etv.effective_time_status = 'UNKNOWN'
                """,
                (valid_from, raw_event_id),
            )
            updated = cur.rowcount
            cur.execute(
                """
                UPDATE evidence
                   SET event_time = COALESCE(event_time, %s),
                       effective_time = COALESCE(effective_time, %s)
                 WHERE raw_event_id = %s
                """,
                (valid_from, valid_from, raw_event_id),
            )
            conn.commit()
            print(f"Dated {updated} temporal version(s) from the manifest generated_at.")
            return 0
    except Exception as exc:
        conn.rollback()
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
