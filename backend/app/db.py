"""
backend/app/db.py
─────────────────
Supabase / PostgreSQL connection pool for Kairos.

Usage
─────
    from backend.app.db import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()

The pool is created once at import time using the DATABASE_URL env var
(loaded from .env if present).  All routes import `get_conn` and use it
as a context manager – the connection is returned to the pool automatically.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

# ── Load .env (no-op if already in environment) ──────────────────────────────
# Walk up from this file's directory until we find a .env file (or run out of parents)
def _find_env_file() -> Path | None:
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        env = candidate / ".env"
        if env.exists():
            return env
    return None

_env_file = _find_env_file()
if _env_file:
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_env_file, override=False)
    except ImportError:
        pass  # python-dotenv not installed; rely on real env vars

# ── Read connection string ────────────────────────────────────────────────────
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# ── Connection pool (lazy singleton) ─────────────────────────────────────────
_pool: pg_pool.ThreadedConnectionPool | None = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    """Return (and lazily create) the shared connection pool."""
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Create a .env file in the repo root with DATABASE_URL=<supabase-url>."
            )
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
            # Supabase pooler (port 6543) uses transaction-mode PgBouncer;
            # keep connections short-lived and do not use server-side cursors.
            connect_timeout=10,
        )
    return _pool


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a connection from the pool; return it when done.

    Example::

        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, name FROM dataset LIMIT 10")
                rows = cur.fetchall()
    """
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


class _PooledConnectionCompat:
    """Pooled psycopg2 connection exposed with the connection API expected by
    the audit / owner / metadata route modules.

    Those modules call ``get_db_connection()`` and then use
    ``conn.cursor(row_factory=dict)``, ``conn.commit()``, ``conn.rollback()``
    and ``conn.close()``.  ``close()`` returns the connection to the pool
    instead of closing it, and discards any uncommitted work.
    """

    def __init__(self, pool: pg_pool.ThreadedConnectionPool, conn) -> None:
        self._pool = pool
        self._conn = conn
        self._returned = False

    def cursor(self, *args, **kwargs):
        row_factory = kwargs.pop("row_factory", None)
        if row_factory is not None and "cursor_factory" not in kwargs:
            kwargs["cursor_factory"] = RealDictCursor
        return self._conn.cursor(*args, **kwargs)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._returned:
            return
        self._returned = True
        conn = self._conn
        try:
            if conn.closed:
                self._pool.putconn(conn, close=True)
            else:
                conn.rollback()  # drop any uncommitted work
                self._pool.putconn(conn)
        except Exception:
            pass

    def __del__(self) -> None:
        """Safety net: routes call ``conn.close()`` inside their ``try`` block,
        so an exception raised mid-query skips it.  Returning the connection
        here guarantees it is never permanently leaked from the pool."""
        try:
            self.close()
        except Exception:
            pass

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_conn"), name)


def get_db_connection() -> _PooledConnectionCompat:
    """Return a pooled connection for the audit / owner / metadata routes."""
    pool = _get_pool()
    return _PooledConnectionCompat(pool, pool.getconn())


def health_check() -> dict:
    """Quick connectivity check used by /health endpoint."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"db": "connected"}
    except Exception as exc:
        return {"db": f"error: {exc}"}
