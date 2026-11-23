"""Seed persisted pipeline-run records for the authenticated demo workspace.

The Pipeline runs page reads ``job`` + ``execution_run`` rows.  The demo
workspace had none, so the page showed an empty execution history.  These
records are demonstration metadata: they describe scheduled revenue and
customer-360 jobs and their outcomes, and each run also stores one immutable
source event so the stored-event count is real rather than invented.

Asset counts stay zero on purpose: this workspace has no normalized runtime
evidence for these runs, and the page must not imply that an event was
observed for a specific dataset when none was stored.

Usage
-----
    python scripts/db/seed_demo_runs.py --workspace <uuid>
    python scripts/db/seed_demo_runs.py --workspace <uuid> --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

ROOT = Path(__file__).resolve().parents[2]

RUNS = (
    {
        "run_id": "demo-run-revenue-20261123-0200",
        "job": "Revenue daily pipeline",
        "environment": "production",
        "status": "completed",
        "started": "2026-11-23T02:00:00Z",
        "completed": "2026-11-23T02:08:42Z",
        "event_type": "COMPLETE",
    },
    {
        "run_id": "demo-run-customer360-20261123-0230",
        "job": "Customer 360 refresh",
        "environment": "production",
        "status": "completed",
        "started": "2026-11-23T02:30:00Z",
        "completed": "2026-11-23T02:41:10Z",
        "event_type": "COMPLETE",
    },
    {
        "run_id": "demo-run-revenue-quality-20261123-0300",
        "job": "Revenue quality gate",
        "environment": "staging",
        "status": "warning",
        "started": "2026-11-23T03:00:00Z",
        "completed": "2026-11-23T03:02:15Z",
        "event_type": "COMPLETE",
    },
    {
        "run_id": "demo-run-legacy-export-20261123-0315",
        "job": "Legacy warehouse export",
        "environment": "production",
        "status": "failed",
        "started": "2026-11-23T03:15:00Z",
        "completed": "2026-11-23T03:16:05Z",
        "event_type": "FAIL",
    },
)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Workspace UUID to seed")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args(argv)

    load_dotenv(dotenv_path=str(ROOT / ".env"))
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"DRY RUN: would upsert {len(RUNS)} runs and {len(RUNS)} raw events.")
        for run in RUNS:
            print(f"  {run['run_id']}  {run['status']:8}  {run['job']}")
        return 0

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (args.workspace,))
            for run in RUNS:
                cur.execute(
                    """
                    INSERT INTO job (workspace_id, namespace, name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (workspace_id, namespace, name)
                    DO UPDATE SET name = EXCLUDED.name
                    RETURNING id::text AS id
                    """,
                    (args.workspace, run["environment"], run["job"]),
                )
                job_id = cur.fetchone()["id"]
                cur.execute(
                    """
                    INSERT INTO execution_run
                        (workspace_id, run_id, job_id, status, started_at, completed_at)
                    VALUES (%s, %s, %s::uuid, %s, %s, %s)
                    ON CONFLICT (workspace_id, run_id)
                    DO UPDATE SET job_id = EXCLUDED.job_id,
                                  status = EXCLUDED.status,
                                  started_at = EXCLUDED.started_at,
                                  completed_at = EXCLUDED.completed_at
                    """,
                    (
                        args.workspace, run["run_id"], job_id, run["status"],
                        _timestamp(run["started"]), _timestamp(run["completed"]),
                    ),
                )
                payload = {
                    "eventType": run["event_type"],
                    "eventTime": run["completed"],
                    "run": {
                        "runId": run["run_id"],
                        "job": {"namespace": run["environment"], "name": run["job"]},
                    },
                    "producer": "kairos-demo-seed",
                }
                cur.execute(
                    """
                    INSERT INTO raw_event
                        (workspace_id, event_id, payload, payload_hash, source_system)
                    VALUES (%s, %s, %s, %s, 'demo_seed')
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        args.workspace, "demo-run-event:" + run["run_id"],
                        Json(payload),
                        hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                    ),
                )
        conn.commit()
        print(f"Seeded {len(RUNS)} demo runs and their source events into {args.workspace}.")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
