#!/usr/bin/env python
"""Operator CLI: verify that all Kairos migrations are applied to the database.

This script connects to the database and confirms that every table created by
migrations 0001-0009 actually exists in the live database.

Exit codes:
    0  all expected tables exist in the database
    1  one or more migrations appear not to be applied (missing tables)
    2  DATABASE_URL is missing (setup error)
    3  database connection failed

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
EXIT_NO_CONNECTION = 3

# Tables created by each migration, in order.
MIGRATIONS = {
    "0001_auth_and_workspace": ["kairos_workspace"],
    "0002_rls_groundwork": [],
    "0003_personal_workspaces": [
        "dataset", "column_record", "job", "execution_run", "raw_event",
        "evidence", "lineage_edge", "edge_temporal_version", "execution_state",
        "projection_outbox", "team_member", "owner_assignment", "owner_request",
        "audit_log", "asset_version", "audit_event", "rollback_record"
    ],
    "0004_ingestion_import_runs": ["import_run"],
    "0005_personalization": ["asset_view", "asset_star"],
    "0006_github_connections": ["github_connection"],
    "0007_membership_roles": ["workspace_member", "workspace_invite"],
    "0008_source_connections": ["source_connection"],
    "0009_governance": ["freshness_sla", "freshness_evaluation", "incident", "incident_event"],
}

ALL_EXPECTED_TABLES = set()
for tables in MIGRATIONS.values():
    ALL_EXPECTED_TABLES.update(tables)


def main(argv=None) -> int:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print(
            "ERROR: DATABASE_URL is not set. Create a .env file in the repo root "
            "with DATABASE_URL=<supabase-url>, or export the variable.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    conn = None
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            )
            live_tables = {row[0] for row in cur.fetchall()}
    except Exception as exc:
        print(f"ERROR: could not connect to database: {exc}", file=sys.stderr)
        return EXIT_NO_CONNECTION
    finally:
        if conn is not None:
            conn.close()

    # Check which tables are missing
    missing = ALL_EXPECTED_TABLES - live_tables
    extra = live_tables - ALL_EXPECTED_TABLES

    print("=" * 70)
    print("Kairos Migration Application Verification")
    print("=" * 70)
    print()

    # Report by migration
    for migration_name, tables in MIGRATIONS.items():
        if not tables:
            status = "[OK]"
        else:
            missing_in_mig = [t for t in tables if t in missing]
            if missing_in_mig:
                status = "[FAIL]"
            else:
                status = "[OK]"
        
        table_summary = f"{len(tables)} table(s)" if tables else "DDL only"
        print(f"{status} {migration_name:40s} {table_summary}")

    print()
    print(f"Expected tables: {len(ALL_EXPECTED_TABLES)}")
    print(f"Live tables:    {len(live_tables)}")
    print()

    if missing:
        print("MISSING (not applied):")
        for table in sorted(missing):
            print(f"  - {table}")
        print()

    if extra:
        print("EXTRA (in database but not in expected list):")
        for table in sorted(extra):
            print(f"  + {table}")
        print()

    print("-" * 70)

    if missing:
        print("RESULT: FAIL — Some migrations appear not to be applied")
        return EXIT_FAILED

    if extra:
        print(f"WARNING: Database has {len(extra)} extra table(s) not in migration list")
        print("         (This is acceptable if they are user-created or from other systems)")
        print()

    print("RESULT: PASS — All expected migrations are applied")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
