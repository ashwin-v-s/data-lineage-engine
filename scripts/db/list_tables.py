#!/usr/bin/env python
"""Operator CLI: list the tables in the database's ``public`` schema.

Connects to the database named by ``DATABASE_URL`` (from the environment or a
repo-root ``.env``) and prints every table in the ``public`` schema.

Exit codes:

    0  connection succeeded and at least one table was listed
    1  connection failed, the query failed, or the schema holds no tables
    2  DATABASE_URL is missing (setup error)

The module has no import-time side effects; all work happens in ``main``.

Usage
-----
    python scripts/db/list_tables.py
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def main(argv=None) -> int:
    # .env is loaded lazily so importing this module never touches the
    # filesystem or the environment.
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
            rows = cur.fetchall()
    except Exception as exc:  # pragma: no cover - depends on live database
        print(f"ERROR: could not list tables: {exc}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        if conn is not None:
            conn.close()

    if not rows:
        print(
            "ERROR: the public schema contains no tables; nothing was listed.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    print("Tables in public schema:")
    for row in rows:
        print(f"  {row[0]}")
    print(f"Listed {len(rows)} table(s)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
