#!/usr/bin/env python
"""Exercise cross-workspace read/write isolation in a rollback-only DB transaction.

Uses the configured migration connection only to create two temporary personal
workspace rows, then switches to the same ``kairos_app`` role used by the API.
All test records are rolled back, including the temporary workspaces.
"""
from __future__ import annotations

import os
import sys
import uuid

import psycopg2
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is required", file=sys.stderr)
        return 2

    owner_a, owner_b = str(uuid.uuid4()), str(uuid.uuid4())
    marker_a, marker_b = f"kairos_isolation_{uuid.uuid4().hex}", f"kairos_isolation_{uuid.uuid4().hex}"
    conn = None
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        conn.autocommit = False
        with conn.cursor() as cur:
            # SECURITY DEFINER provisions a workspace without leaving test rows
            # behind; the entire connection transaction is rolled back below.
            cur.execute("SELECT kairos_ensure_personal_workspace(%s::uuid)", (owner_a,))
            workspace_a = str(cur.fetchone()[0])
            cur.execute("SELECT kairos_ensure_personal_workspace(%s::uuid)", (owner_b,))
            workspace_b = str(cur.fetchone()[0])
            if workspace_a == workspace_b:
                raise RuntimeError("test workspaces unexpectedly resolved to the same id")

            cur.execute("SET LOCAL ROLE kairos_app")
            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (workspace_a,))
            cur.execute(
                """INSERT INTO dataset
                   (source_system,namespace,database_name,schema_name,name,asset_type)
                   VALUES ('isolation-test','kairos','test','public',%s,'table')
                   RETURNING id::text""",
                (marker_a,),
            )
            asset_a = cur.fetchone()[0]

            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (workspace_b,))
            cur.execute("SELECT count(*) FROM dataset WHERE id=%s::uuid", (asset_a,))
            if cur.fetchone()[0] != 0:
                raise RuntimeError("workspace B read workspace A's dataset")

            cur.execute("SAVEPOINT cross_workspace_write")
            try:
                cur.execute(
                    """INSERT INTO dataset
                       (workspace_id,source_system,namespace,database_name,schema_name,name,asset_type)
                       VALUES (%s::uuid,'isolation-test','kairos','test','public',%s,'table')""",
                    (workspace_a, marker_b),
                )
            except psycopg2.errors.InsufficientPrivilege:
                cur.execute("ROLLBACK TO SAVEPOINT cross_workspace_write")
            else:
                raise RuntimeError("workspace B inserted a dataset into workspace A")
            cur.execute("RELEASE SAVEPOINT cross_workspace_write")

            cur.execute(
                "UPDATE dataset SET name=%s WHERE id=%s::uuid RETURNING id",
                (marker_b, asset_a),
            )
            if cur.fetchone() is not None:
                raise RuntimeError("workspace B updated workspace A's dataset")

            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (workspace_a,))
            cur.execute("SELECT count(*) FROM dataset WHERE id=%s::uuid", (asset_a,))
            if cur.fetchone()[0] != 1:
                raise RuntimeError("workspace A could not read its own dataset")

        conn.rollback()
        print("PASS: kairos_app cannot read, insert into, or update another workspace.")
        print("PASS: the owning workspace can read its own test dataset.")
        print("PASS: temporary workspaces and datasets were rolled back.")
        return 0
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        print(f"FAIL: workspace isolation check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
