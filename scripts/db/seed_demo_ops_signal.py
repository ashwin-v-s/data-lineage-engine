"""Seed one reproducible operational signal in the authenticated demo workspace.

The freshness engine only opens an incident from stored evidence.  This script
records a manual confirmation older than the demo SLA, then invokes the same
evaluation handler used by the API.  The resulting freshness evaluation,
incident, incident event and in-app notification are all workspace-scoped rows;
nothing is fabricated at render time.

Usage:
    python scripts/db/seed_demo_ops_signal.py --workspace <uuid>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from psycopg2.extras import RealDictCursor  # noqa: E402

from backend.app.api.routes.governance import evaluate_dataset  # noqa: E402
from backend.app.db import get_conn, reset_workspace_id, set_workspace_id  # noqa: E402

DEMO_NOTE = "Demo stale signal: source confirmation is older than the 120-minute SLA."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Workspace UUID")
    args = parser.parse_args()

    token = set_workspace_id(args.workspace)
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT user_id::text FROM workspace_member WHERE role='owner' AND status='active' ORDER BY created_at LIMIT 1"
                )
                owner = cur.fetchone()
                if not owner:
                    raise RuntimeError("No active owner in this workspace")
                owner_id = owner["user_id"]

                cur.execute(
                    "SELECT id::text, name, owner_id FROM dataset "
                    "WHERE name='customers' AND asset_type='TABLE' AND removed_at IS NULL LIMIT 1"
                )
                dataset = cur.fetchone()
                if not dataset:
                    raise RuntimeError("customers TABLE not found in this workspace")
                if dataset["owner_id"] != owner_id:
                    cur.execute("UPDATE dataset SET owner_id=%s WHERE id=%s::uuid", (owner_id, dataset["id"]))

                cur.execute(
                    """
                    INSERT INTO freshness_sla
                        (dataset_id, warn_after_minutes, error_after_minutes,
                         stale_after_minutes, signal, evaluation_schedule)
                    VALUES (%s::uuid, 48, 60, 120, 'manual', 'manual')
                    ON CONFLICT (workspace_id, dataset_id) DO UPDATE
                      SET warn_after_minutes=48, error_after_minutes=60,
                          stale_after_minutes=120, signal='manual',
                          evaluation_schedule='manual', paused=false
                    """,
                    (dataset["id"],),
                )
                cur.execute(
                    "DELETE FROM freshness_confirmation WHERE dataset_id=%s::uuid AND note LIKE 'Demo stale signal:%%'",
                    (dataset["id"],),
                )
                cur.execute(
                    """
                    INSERT INTO freshness_confirmation
                        (dataset_id, observed_at, note, confirmed_by)
                    VALUES (%s::uuid, now() - interval '180 minutes', %s, %s::uuid)
                    """,
                    (dataset["id"], DEMO_NOTE, owner_id),
                )
        # The manual confirmation is committed above; evaluate in the same
        # workspace context so the incident and notification are workspace rows.
        actor_email = os.getenv("KAIROS_DEMO_EMAIL") or owner_id
        result = evaluate_dataset(dataset["id"], user={"id": owner_id, "email": actor_email})
    finally:
        reset_workspace_id(token)

    print(
        f"evaluated {dataset['name']}: state={result['verdict']['state']} "
        f"incident={result['incident_action']} id={result['incident_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
