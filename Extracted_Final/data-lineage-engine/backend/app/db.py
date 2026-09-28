"""
Database connection module for KAIROS.
Uses psycopg2 to connect to Supabase (PostgreSQL).
Reads DATABASE_URL from .env file.
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

# Load .env from repo root (two levels up from this file)
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env")
load_dotenv(dotenv_path=_env_path)

# Also try local .env
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/kairos"
)


def get_connection():
    """Get a raw psycopg2 connection to Supabase."""
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def get_cursor():
    """
    Context manager that yields a cursor with RealDictCursor
    so rows come back as dicts instead of tuples.
    Auto-commits and closes connection.

    Usage:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM dataset")
            rows = cur.fetchall()
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


def health_check() -> bool:
    """Returns True if database is reachable, False otherwise."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            return True
    except Exception:
        return False
