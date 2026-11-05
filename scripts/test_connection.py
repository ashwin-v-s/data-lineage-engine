#!/usr/bin/env python
"""Operator CLI: verify that ``DATABASE_URL`` reaches a live PostgreSQL.

Connects to the database named by ``DATABASE_URL`` (from the environment or a
repo-root ``.env``) and asks the server for its version and database name.

Exit codes:

    0  connection succeeded and the server answered both queries
    1  connection or query failed
    2  DATABASE_URL is missing (setup error)

The module has no import-time side effects; all work happens in ``main``.

Usage
-----
    python scripts/test_connection.py
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

    print("Connecting to PostgreSQL...")
    conn = None
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            row = cur.fetchone()
            if row is None:
                print(
                    "ERROR: connected but the server returned no version row.",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            print(f"Connected! PostgreSQL version: {row[0][:50]}")

            cur.execute("SELECT current_database();")
            db_row = cur.fetchone()
            if db_row is None:
                print(
                    "ERROR: connected but the server returned no database row.",
                    file=sys.stderr,
                )
                return EXIT_FAILED
            print(f"Database: {db_row[0]}")
    except Exception as exc:  # pragma: no cover - depends on live database
        print(f"ERROR: connection test failed: {exc}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        if conn is not None:
            conn.close()

    print("Connection test PASSED")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
