"""Environment resolution for the Supabase settings the API depends on.

Hosting providers do not all use the same variable names.  Vercel's Supabase
integration exports ``NEXT_PUBLIC_SUPABASE_URL`` / ``SUPABASE_ANON_KEY`` and a
pooled ``POSTGRES_URL``, while this repository documents
``SUPABASE_URL`` / ``SUPABASE_PUBLISHABLE_KEY`` / ``DATABASE_URL``.  Reading the
first non-empty alias keeps a hosted deployment working regardless of which
naming the dashboard uses, instead of silently serving an empty sign-in config.

Only public, browser-safe Supabase values are resolved here: the publishable
(anon) key is safe to expose, while the ``service_role`` key is deliberately
never considered.
"""
from __future__ import annotations

import os

_SUPABASE_URL_VARS = (
    "SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_URL",
    "VITE_SUPABASE_URL",
)

# Ordered by preference; all of these are publishable/anon keys.
_SUPABASE_KEY_VARS = (
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "VITE_SUPABASE_PUBLISHABLE_KEY",
    "VITE_SUPABASE_ANON_KEY",
)

# Pooled connection strings first: serverless functions must not open direct
# database connections.  ``POSTGRES_URL_NON_POOLING`` is a last-resort fallback.
_DATABASE_URL_VARS = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_PRISMA_URL",
    "SUPABASE_DB_URL",
    "POSTGRES_URL_NON_POOLING",
)


def env_value(*names: str) -> str | None:
    """Return the first non-empty, trimmed value among ``names``."""
    for name in names:
        value = (os.getenv(name) or "").strip().strip('"').strip("'").strip()
        if value:
            return value
    return None


def supabase_url() -> str | None:
    """Public Supabase project URL, without a trailing slash."""
    value = env_value(*_SUPABASE_URL_VARS)
    return value.rstrip("/") if value else None


def supabase_publishable_key() -> str | None:
    """Publishable (anon) key sent as the Supabase ``apikey`` header."""
    return env_value(*_SUPABASE_KEY_VARS)


def database_url() -> str | None:
    """Postgres connection string used by the API's connection pool."""
    return env_value(*_DATABASE_URL_VARS)
