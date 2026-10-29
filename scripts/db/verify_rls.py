#!/usr/bin/env python
"""Operator CLI: verify row-level-security hardening of the Kairos business tables.

This script is meant to be used as a release gate.  It connects to the database
named by ``DATABASE_URL`` and, for every workspace-scoped business table defined
by the Kairos migrations, asserts and reports:

  (a) row-level security is enabled              -> pg_class.relrowsecurity
  (b) row-level security is forced               -> pg_class.relforcerowsecurity
  (c) at least one policy is defined             -> pg_policies
  (d) a NOT NULL ``workspace_id`` column exists  -> information_schema.columns

It additionally asserts that the connecting role cannot bypass RLS
(``pg_roles.rolbypassrls`` for ``current_user``).

Each table prints a single PASS/FAIL line (a FAIL is followed by the failing
reasons, indented) and the run ends with a summary.  The process exits non-zero
when any check fails, so CI can gate a release on it.

Usage
-----
    python scripts/db/verify_rls.py
    python scripts/db/verify_rls.py --schema public
    python scripts/db/verify_rls.py --table dataset evidence

The module has no import-time side effects; all work happens in ``main``.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

# Workspace-scoped business tables that must be hardened.  Hard-coded from the
# Kairos migrations:
#   * 0003_personal_workspaces.sql - the "ALTER TABLE ... ENABLE/FORCE ROW LEVEL
#     SECURITY" loop over the 17 business tables.
#   * 0005_personalization.sql     - asset_view, asset_star.
#   * 0006_github_connections.sql  - github_connection.
#
# 0004_ingestion_import_runs.sql (import_run) is intentionally omitted because it
# is marked "PROPOSAL ONLY: NOT APPLIED" and would otherwise break the gate on
# the shared project.  0006_github_connections.sql is *also* still a proposal,
# but its github_connection table is listed here because it previously slipped
# past this gate entirely; run this check only against a database where 0006 has
# been applied, otherwise github_connection is reported as missing.  See
# backend/migrations/README.md for per-migration apply status, and
# scripts/db/check_migrations.py for the static cross-check that keeps this list
# in sync with the migrations.
WORKSPACE_SCOPED_TABLES = (
    # 0003_personal_workspaces.sql
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
    "team_member",
    "owner_assignment",
    "owner_request",
    "audit_log",
    "asset_version",
    "audit_event",
    "rollback_record",
    # 0005_personalization.sql
    "asset_view",
    "asset_star",
    # 0006_github_connections.sql
    "github_connection",
)

# Exit codes.
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def _fetch_table_flags(cur, schema: str, table: str):
    """Return (relrowsecurity, relforcerowsecurity) or None when missing.

    Only ordinary and partitioned tables are considered business tables.
    """
    cur.execute(
        """
        SELECT c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s
          AND c.relname = %s
          AND c.relkind IN ('r', 'p')
        """,
        (schema, table),
    )
    return cur.fetchone()


def _fetch_policy_names(cur, schema: str, table: str):
    """Return the list of RLS policy names defined on the table."""
    cur.execute(
        """
        SELECT policyname
        FROM pg_policies
        WHERE schemaname = %s
          AND tablename = %s
        ORDER BY policyname
        """,
        (schema, table),
    )
    return [row[0] for row in cur.fetchall()]


def _fetch_workspace_column(cur, schema: str, table: str):
    """Return the is_nullable flag ('YES'/'NO') for workspace_id, or None."""
    cur.execute(
        """
        SELECT is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = 'workspace_id'
        """,
        (schema, table),
    )
    row = cur.fetchone()
    return row[0] if row else None


def check_table(cur, schema: str, table: str):
    """Run every RLS assertion for one table.

    Returns a list of human-readable failure reasons; an empty list means PASS.
    """
    failures = []

    flags = _fetch_table_flags(cur, schema, table)
    if flags is None:
        failures.append(
            f"table {schema}.{table} was not found (expected a business table)"
        )
        return failures

    relrowsecurity, relforcerowsecurity = flags
    if not relrowsecurity:
        failures.append("row-level security is not enabled (relrowsecurity = false)")
    if not relforcerowsecurity:
        failures.append(
            "row-level security is not forced (relforcerowsecurity = false)"
        )

    policies = _fetch_policy_names(cur, schema, table)
    if not policies:
        failures.append("no row-level security policy is defined")

    is_nullable = _fetch_workspace_column(cur, schema, table)
    if is_nullable is None:
        failures.append("workspace_id column is missing")
    elif is_nullable != "NO":
        failures.append("workspace_id column is nullable (expected NOT NULL)")

    return failures


def check_connecting_role(cur):
    """Return (role_name, rolbypassrls) for the connecting role, or None."""
    cur.execute(
        "SELECT current_user, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    )
    return cur.fetchone()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_rls.py",
        description=(
            "Verify row-level-security hardening of the Kairos business tables. "
            "Exits non-zero when any check fails."
        ),
    )
    parser.add_argument(
        "--schema",
        default="public",
        help="database schema that holds the Kairos business tables (default: public)",
    )
    parser.add_argument(
        "--table",
        dest="tables",
        nargs="+",
        metavar="TABLE",
        help=(
            "verify only the named workspace-scoped tables "
            "(default: every known business table)"
        ),
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Selecting a table that is not a known workspace-scoped business table is a
    # usage error; the list is fixed by the migrations.
    if args.tables:
        unknown = [t for t in args.tables if t not in WORKSPACE_SCOPED_TABLES]
        if unknown:
            print(
                "ERROR: unknown table(s): "
                + ", ".join(unknown)
                + "\nKnown tables: "
                + ", ".join(WORKSPACE_SCOPED_TABLES),
                file=sys.stderr,
            )
            return EXIT_USAGE
        tables = [t for t in WORKSPACE_SCOPED_TABLES if t in set(args.tables)]
    else:
        tables = list(WORKSPACE_SCOPED_TABLES)

    # .env is loaded lazily so importing this module never touches the filesystem
    # or the environment.
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print(
            "ERROR: DATABASE_URL is not set. Create a .env file in the repo root "
            "with DATABASE_URL=<supabase-url>, or export the variable.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
    except Exception as exc:  # pragma: no cover - depends on live database
        print(f"ERROR: could not connect using DATABASE_URL: {exc}", file=sys.stderr)
        return EXIT_USAGE

    failures_by_table = {}
    role_failures = []
    try:
        with conn.cursor() as cur:
            role_row = check_connecting_role(cur)
            if role_row is None:
                role_failures.append(
                    "connecting role could not be resolved in pg_roles"
                )
                role_name, role_bypass = "(unknown)", None
            else:
                role_name, role_bypass = role_row
                if role_bypass:
                    role_failures.append(
                        f"connecting role '{role_name}' can bypass RLS "
                        "(rolbypassrls = true)"
                    )

            for table in tables:
                failures_by_table[table] = check_table(cur, args.schema, table)
    finally:
        conn.close()

    width = 66
    print("=" * width)
    print("Kairos row-level-security verification")
    print("=" * width)
    print(f"Connecting role : {role_name}")
    print(f"Schema          : {args.schema}")
    print(f"Tables checked  : {len(tables)}")
    print("-" * width)

    if role_failures:
        print("[FAIL] connecting role")
        for reason in role_failures:
            print(f"       - {reason}")
    else:
        print(f"[PASS] connecting role '{role_name}' cannot bypass RLS")
    print("")

    passed = 0
    for table in tables:
        failures = failures_by_table[table]
        if failures:
            print(f"[FAIL] {table}")
            for reason in failures:
                print(f"       - {reason}")
        else:
            passed += 1
            print(f"[PASS] {table}")

    total = len(tables)
    failed = total - passed
    print("-" * width)
    print(f"Summary: {passed}/{total} tables passed, {failed} failed")

    ok = failed == 0 and not role_failures
    if ok:
        print("RESULT: PASS")
        return EXIT_OK

    print("RESULT: FAIL")
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
