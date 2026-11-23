"""Workspace API keys (migration 0016).

Owners and admins mint read-only keys for machine clients.  The secret is
returned once at creation; afterwards only its display prefix, scopes and use
timestamps are readable.  Authentication itself lives in ``backend.app.auth``,
which resolves a ``kairos_sk_`` bearer token against the stored hash.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from psycopg2 import Error as PostgresError
from pydantic import BaseModel, Field

from backend.app.api.routes.membership import require_role
from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.services.api_keys import generate_api_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"], dependencies=[Depends(require_user)])

_UNPROVISIONED_DETAIL = "API keys are not provisioned (migration 0016 not applied)"


def _table_missing(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    row = cur.fetchone()
    return row is None or row[0] is None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


def _serialise(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "prefix": row[2],
        "scopes": list(row[3] or []),
        "created_at": row[4].isoformat() if row[4] else None,
        "last_used_at": row[5].isoformat() if row[5] else None,
        "revoked_at": row[6].isoformat() if row[6] else None,
    }


@router.get("")
def list_api_keys():
    """List active keys for the workspace. Secrets are never returned."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_api_key"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                SELECT id::text, name, token_prefix, scopes, created_at, last_used_at, revoked_at
                FROM workspace_api_key
                WHERE workspace_id = current_setting('kairos.workspace_id', true)::uuid
                  AND revoked_at IS NULL
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()
    return {"ok": True, "keys": [_serialise(r) for r in rows]}


@router.get("/self")
def read_own_key(user: dict = Depends(require_user)):
    """Return the calling key's own metadata.

    This is the endpoint a machine client uses to verify that a key works; it
    is one of the paths allowed to key-authenticated callers.
    """
    key_id = user.get("api_key_id")
    if user.get("auth") != "api_key" or not key_id:
        raise HTTPException(status_code=400, detail="This endpoint requires an API key")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, name, token_prefix, scopes, created_at, last_used_at, revoked_at
                FROM workspace_api_key
                WHERE id = %s::uuid
                  AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                """,
                (str(key_id),),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"ok": True, "key": _serialise(row), "auth": "api_key"}


@router.post("", status_code=201, dependencies=[Depends(require_role("owner", "admin"))])
def create_api_key(body: ApiKeyCreate, user: dict = Depends(require_user)):
    token, prefix, secret_hash = generate_api_key()
    actor_id = user.get("id") or user.get("sub")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if _table_missing(cur, "workspace_api_key"):
                    raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
                # Revoking a key keeps its audit row, so the name is normally
                # still present.  Reusing the name must rotate that row instead
                # of failing as a duplicate: the UI promises a lost key can be
                # replaced, and the old secret must stay dead.
                cur.execute(
                    """
                    SELECT id::text, revoked_at
                    FROM workspace_api_key
                    WHERE workspace_id = current_setting('kairos.workspace_id', true)::uuid
                      AND name = %s
                    FOR UPDATE
                    """,
                    (body.name.strip(),),
                )
                existing = cur.fetchone()
                if existing and existing[1] is None:
                    raise HTTPException(status_code=409, detail="A key with that name already exists")
                if existing:
                    cur.execute(
                        """
                        UPDATE workspace_api_key
                           SET token_prefix = %s,
                               secret_hash = %s,
                               scopes = ARRAY['read']::text[],
                               created_by = %s::uuid,
                               created_at = now(),
                               last_used_at = NULL,
                               revoked_at = NULL
                         WHERE id = %s::uuid
                        RETURNING id::text, name, token_prefix, scopes, created_at, last_used_at, revoked_at
                        """,
                        (prefix, secret_hash, str(actor_id), existing[0]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO workspace_api_key
                            (workspace_id, name, token_prefix, secret_hash, scopes, created_by)
                        VALUES (
                            current_setting('kairos.workspace_id', true)::uuid,
                            %s, %s, %s, ARRAY['read']::text[], %s::uuid
                        )
                        RETURNING id::text, name, token_prefix, scopes, created_at, last_used_at, revoked_at
                        """,
                        (body.name.strip(), prefix, secret_hash, str(actor_id)),
                    )
                row = cur.fetchone()
    except PostgresError as exc:
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="A key with that name already exists") from exc
        raise
    return {
        "ok": True,
        "key": _serialise(row),
        # The only time the secret is ever returned.
        "token": token,
    }


@router.delete("/{key_id}")
def revoke_api_key(key_id: uuid.UUID, user: dict = Depends(require_role("owner", "admin"))):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_api_key"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                UPDATE workspace_api_key
                   SET revoked_at = now()
                 WHERE id = %s::uuid
                   AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                   AND revoked_at IS NULL
                RETURNING id::text
                """,
                (str(key_id),),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found or already revoked")
    return {"ok": True, "id": row[0], "revoked": True}
