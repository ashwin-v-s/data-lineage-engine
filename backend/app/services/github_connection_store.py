"""
backend/app/services/github_connection_store.py
───────────────────────────────────────────────
Persistence for workspace-scoped private GitHub App connections.

Design rules
────────────
* Every function operates through ``get_conn`` so the ``kairos.workspace_id``
  session GUC and the ``kairos_app`` role apply to each statement; row-level
  security confines reads and writes to the caller's workspace.
* The stored credential is always the AES-256-GCM envelope produced by
  :mod:`backend.app.services.token_crypto`.  This module never receives or
  returns plaintext tokens, and the ciphertext column is excluded from every
  projection returned to callers.
* Only non-secret columns are echoed back, so a route can never leak token
  material by returning a store result verbatim.
"""
from __future__ import annotations

from typing import Optional

from psycopg2.extras import Json, RealDictCursor

from backend.app.db import get_conn

# Columns safe to return to callers; token_ciphertext is deliberately absent.
_PUBLIC_COLUMNS = """
    id::text            AS id,
    installation_id     AS installation_id,
    account_login       AS account_login,
    account_type        AS account_type,
    token_expires_at    AS token_expires_at,
    scopes              AS scopes,
    permissions         AS permissions,
    created_at          AS created_at,
    updated_at          AS updated_at
"""


def _serialize(row: dict) -> dict:
    """Return the row with datetime fields rendered as ISO-8601 strings."""
    data = dict(row)
    for key in ("token_expires_at", "created_at", "updated_at"):
        value = data.get(key)
        if value is not None:
            data[key] = value.isoformat()
    return data


def upsert_connection(
    *,
    user_id: str,
    installation_id: int,
    account_login: Optional[str],
    account_type: Optional[str],
    token_ciphertext: bytes,
    token_key_version: int,
    token_expires_at=None,
    scopes: Optional[str] = None,
    permissions: Optional[dict] = None,
) -> dict:
    """Insert or refresh the connection for ``installation_id``.

    ``token_ciphertext`` must already be the encrypted envelope; this function
    performs no encryption and never persists plaintext.  Returns the
    non-secret summary of the stored row.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                INSERT INTO github_connection (
                    user_id, installation_id, account_login, account_type,
                    token_ciphertext, token_key_version, token_expires_at,
                    scopes, permissions, created_at, updated_at
                )
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                ON CONFLICT (workspace_id, installation_id) DO UPDATE SET
                    user_id           = EXCLUDED.user_id,
                    account_login     = EXCLUDED.account_login,
                    account_type      = EXCLUDED.account_type,
                    token_ciphertext  = EXCLUDED.token_ciphertext,
                    token_key_version = EXCLUDED.token_key_version,
                    token_expires_at  = EXCLUDED.token_expires_at,
                    scopes            = EXCLUDED.scopes,
                    permissions       = EXCLUDED.permissions,
                    updated_at        = now()
                RETURNING {_PUBLIC_COLUMNS}
                """,
                (
                    user_id,
                    int(installation_id),
                    account_login,
                    account_type,
                    token_ciphertext,
                    int(token_key_version),
                    token_expires_at,
                    scopes,
                    Json(permissions or {}),
                ),
            )
            row = cur.fetchone()
    return _serialize(row)


def list_connections() -> list[dict]:
    """Return the workspace's connections, newest first, without token material."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_PUBLIC_COLUMNS}
                FROM   github_connection
                ORDER  BY created_at DESC
                """
            )
            rows = cur.fetchall()
    return [_serialize(row) for row in rows]


def delete_connection(connection_id: str) -> int:
    """Delete a connection in the caller's workspace; return the deleted count.

    Row-level security confines the delete to the caller's workspace, so a
    ``0`` result means the id is unknown *or* belongs to another workspace.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM github_connection WHERE id = %s::uuid",
                (connection_id,),
            )
            deleted = cur.rowcount
    return int(deleted or 0)
