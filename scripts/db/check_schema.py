#!/usr/bin/env python
"""Operator CLI: print columns of the ``dataset`` table from the live database.

Connects to ``DATABASE_URL`` and lists every column with its data type.  If the
connection fails or the table is missing, the script exits non-zero so CI and
humans see the right status.

Exit codes
----------
    0  connected and table schema printed
    1  connection or query failed
    2  DATABASE_URL is missing (setup error)

Usage
-----
    python scripts/db/check_schema.py
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
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print(
            "ERROR: DATABASE_URL is not set. Create a .env file with "
            "DATABASE_URL=<connection-string>, or export the variable.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    conn = None
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'dataset' "
                "ORDER BY ordinal_position"
            )
            rows = cur.fetchall()
    except Exception as exc:
        print(f"ERROR: could not read schema: {exc}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        if conn is not None:
            conn.close()

    if not rows:
        print(
            "ERROR: the 'dataset' table was not found or has no columns.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    print("Dataset table columns:")
    for row in rows:
        print(f"  {row[0]:<25} {row[1]}")
    print(f"Listed {len(rows)} column(s)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
