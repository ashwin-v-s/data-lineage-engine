#!/usr/bin/env python
"""Operator CLI: verify that each migration's tables exist in the live database.

Unlike ``check_migrations.py`` (which is a static file check with NO database
contact), this script CONNECTS to the database and queries
``information_schema.tables`` to confirm each migration's tables are actually
present in the live project.

A migration header may only say "Applied" once this script exits 0 for its
expected tables.  Never quote ``check_migrations.py``'s ``RESULT: PASS`` as
proof of application — that script never touches a database.

Exit codes
----------
    0  connected AND every expected table exists
    1  connection failed OR one or more tables are missing
    2  DATABASE_URL is missing (setup error)

Usage
-----
    python scripts/db/verify_applied.py
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

# Expected tables per migration.  Update this list whenever a new migration is
# added; the key is the migration file prefix for clarity in the report.
MIGRATION_TABLES: dict[str, list[str]] = {
    "0001_core": [
        "dataset",
        "column_record",
        "job",
        "execution_run",
        "raw_event",
        "evidence",
        "lineage_edge",
        "edge_temporal_version",
        "execution_state",
        "projection_outbox",
    ],
    "0002_audit_ownership_metadata": [
        "team_member",
        "owner_assignment",
        "owner_request",
        "audit_log",
        "asset_version",
        "audit_event",
        "rollback_record",
    ],
    "0003_personal_workspaces": [
        "kairos_workspace",
    ],
    "0004_ingestion_import_runs": [
        "import_run",
    ],
    "0005_personalization": [
        "asset_view",
        "asset_star",
    ],
    "0006_github_connections": [
        "github_connection",
    ],
    "0007_membership_roles": [
        "workspace_member",
        "workspace_invite",
    ],
    "0008_source_connections": [
        "source_connection",
    ],
    "0009_governance": [
        "freshness_sla",
        "freshness_evaluation",
        "incident",
        "incident_event",
    ],
}


def main(argv=None) -> int:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print(
            "ERROR: DATABASE_URL is not set. Create a .env file with "
            "DATABASE_URL=<connection-string>, or export the variable.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    print("Connecting to database to verify applied migrations...")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
    except Exception as exc:
        print(f"ERROR: cannot connect — {exc}", file=sys.stderr)
        print(
            "RESULT: FAIL — could not reach the database. "
            "Fix DATABASE_URL and wait for any circuit-breaker reset.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            live_tables: set[str] = {row[0] for row in cur.fetchall()}
    except Exception as exc:
        print(f"ERROR: query failed — {exc}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        conn.close()

    width = 66
    print("=" * width)
    print("Kairos migration apply verification  (live database check)")
    print("=" * width)
    print(f"Live tables in public schema: {len(live_tables)}")
    print("-" * width)

    total_checked = 0
    missing_by_migration: dict[str, list[str]] = {}

    for migration, tables in MIGRATION_TABLES.items():
        total_checked += len(tables)
        missing = [t for t in tables if t not in live_tables]
        present = [t for t in tables if t in live_tables]

        if missing:
            missing_by_migration[migration] = missing
            print(f"[FAIL] {migration}")
            for t in present:
                print(f"       present : {t}")
            for t in missing:
                print(f"       MISSING : {t}")
        else:
            print(f"[PASS] {migration}  ({len(tables)} table(s))")

    print("-" * width)
    total_missing = sum(len(v) for v in missing_by_migration.values())
    print(f"Tables checked : {total_checked}")
    print(f"Tables missing : {total_missing}")

    if missing_by_migration:
        print("")
        print("Migrations that need to be applied:")
        for m in missing_by_migration:
            print(f"  backend/migrations/{m}.sql")
        print("")
        print("RESULT: FAIL — apply the missing migrations before marking them Applied")
        return EXIT_FAILED

    print("")
    print("RESULT: PASS — all expected tables exist in the live database")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
