#!/usr/bin/env python
"""Operator CLI: verify that each migration's tables exist in the live database.

Unlike ``check_migrations.py`` (which is a static file check with NO database
contact), this script CONNECTS to the database and queries
``information_schema.tables`` to confirm each migration's tables are actually
present in the live project.

A migration header may only say "Applied" once this script exits 0 for its
expected tables.  Never quote ``check_migrations.py``'s ``RESULT: PASS`` as
proof of application — that script never touches a database.

Scope caveat: this script checks table *existence* only.  A PASS means "the
tables listed in :data:`MIGRATION_TABLES` exist", never "the migration files
were executed".  Column/constraint/RLS changes and migration bookkeeping are
out of scope, and migrations listed in :data:`PROPOSAL_ONLY_MIGRATIONS` are
reported as pending rather than counted as applied.

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
#
# Scope of this check: table *existence* only.  It does not look at columns,
# constraints, indexes, RLS state or migration bookkeeping, so a PASS here must
# never be described as "migration NNNN was applied" — only as "the tables this
# entry names exist".  A migration that only ALTERs an existing table (0010 adds
# columns to source_connection and one new table) can only be represented by
# the tables it creates.
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
    "0010_m2_source_connection_lifecycle": [
        # M2's lifecycle migration alters source_connection and adds sync_job.
        "sync_job",
    ],
    "0011_m4_governance": [
        "freshness_confirmation",
        "quality_assertion",
        "quality_result",
        "glossary_term",
        "term_assignment",
        "pii_classification",
        "domain",
        "data_product",
        "product_asset",
        "data_contract",
        "quality_contract_link",
        "notification",
        "notification_preference",
    ],
    "0014_welcome_email_delivery": ["kairos_welcome_email_delivery"],
}

# Migrations whose header says PROPOSAL ONLY / NOT APPLIED.  Their tables are
# reported when absent but do not fail the run, because a proposal is *expected*
# to be unapplied until the migration owner approves it.  Once such a migration
# is approved and applied, remove it from this set so its absence fails again.
PROPOSAL_ONLY_MIGRATIONS: frozenset[str] = frozenset()

# Function-only migrations are verified separately from table presence.
MIGRATION_ROUTINES: dict[str, list[str]] = {
    "0013_membership_lifecycle": [
        "public.kairos_ensure_personal_workspace(uuid)",
        "public.kairos_list_user_workspaces(uuid)",
        "public.kairos_accept_workspace_invite(text,uuid,text)",
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

    live_routines: dict[str, bool] = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            live_tables: set[str] = {row[0] for row in cur.fetchall()}
            for migration, routines in MIGRATION_ROUTINES.items():
                for routine in routines:
                    cur.execute("SELECT to_regprocedure(%s) IS NOT NULL", (routine,))
                    live_routines[routine] = bool(cur.fetchone()[0])
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
    pending_proposals: dict[str, list[str]] = {}

    for migration, tables in MIGRATION_TABLES.items():
        total_checked += len(tables)
        missing = [t for t in tables if t not in live_tables]
        present = [t for t in tables if t in live_tables]
        proposal = migration in PROPOSAL_ONLY_MIGRATIONS

        if missing and proposal:
            pending_proposals[migration] = missing
            print(f"[PENDING] {migration}  (proposal only; not counted as applied)")
            for t in present:
                print(f"       present : {t}")
            for t in missing:
                print(f"       absent  : {t}")
        elif missing:
            missing_by_migration[migration] = missing
            print(f"[FAIL] {migration}")
            for t in present:
                print(f"       present : {t}")
            for t in missing:
                print(f"       MISSING : {t}")
        else:
            print(f"[PASS] {migration}  ({len(tables)} table(s))")

    missing_routines = [routine for routine, present in live_routines.items() if not present]
    for migration, routines in MIGRATION_ROUTINES.items():
        missing = [routine for routine in routines if not live_routines.get(routine, False)]
        if missing:
            print(f"[FAIL] {migration}  (database routine(s) missing)")
            for routine in missing:
                print(f"       MISSING : {routine}")
        else:
            print(f"[PASS] {migration}  ({len(routines)} routine(s))")

    print("-" * width)
    total_missing = sum(len(v) for v in missing_by_migration.values())
    total_pending = sum(len(v) for v in pending_proposals.values())
    print(f"Tables checked : {total_checked}")
    print(f"Tables missing : {total_missing}")
    if total_pending:
        print(f"Tables absent from proposal-only migrations : {total_pending}")

    if missing_by_migration or missing_routines:
        print("")
        print("Migrations that need to be applied:")
        for m in missing_by_migration:
            print(f"  backend/migrations/{m}.sql")
        for m in MIGRATION_ROUTINES:
            if any(not live_routines.get(routine, False) for routine in MIGRATION_ROUTINES[m]):
                print(f"  backend/migrations/{m}.sql")
        print("")
        print("RESULT: FAIL — expected tables are missing; apply the listed "
              "migrations before marking them Applied")
        return EXIT_FAILED

    print("")
    print("RESULT: PASS — every table this script tracks exists in the live database")
    print("Scope: this checks listed table presence and named routine presence. It does not "
          "prove every migration statement, column, constraint, index or RLS policy is present.")
    if pending_proposals:
        print("Not counted as applied (proposal only, awaiting migration-owner "
              "approval): " + ", ".join(sorted(pending_proposals)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
