"""
backend/app/api/routes/membership.py
────────────────────────────────────
Workspace membership and invitations (migration 0007).

Membership is the source of truth for a user's role in a workspace; the role
is never read from the JWT.  Invitations can never grant ownership.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(prefix="/members", tags=["membership"], dependencies=[Depends(require_user)])

_ROLE_ORDER = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}
_INVITABLE_ROLES = ("admin", "editor", "viewer")

_UNPROVISIONED_DETAIL = "Membership storage is not provisioned (migration 0007 not applied)"


def _table_missing(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    row = cur.fetchone()
    return row is None or row[0] is None


def _member_role(conn, workspace_id: str, user_id: str) -> Optional[str]:
    with conn.cursor() as cur:
        if _table_missing(cur, "workspace_member"):
            raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
        cur.execute(
            "SELECT role FROM workspace_member WHERE workspace_id = %s AND user_id = %s AND status = 'active'",
            (workspace_id, user_id),
        )
        row = cur.fetchone()
    return row[0] if row else None


def require_role(*minimum_roles: str):
    """Dependency: the verified user must hold at least one of these roles.

    The inner ``guard`` is a plain function (no nested ``Depends``) so that
    monkeypatching ``membership.get_conn`` in tests works correctly — the
    reference is resolved at call time via the module-level name.
    """
    minimum = {r: _ROLE_ORDER[r] for r in minimum_roles}

    def guard(user: dict = Depends(require_user)):
        user_id = user.get("id") or user.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Authenticated user id is missing")

        from backend.app import db as _db
        workspace_id = _db._workspace_id.get()
        if not workspace_id:
            raise HTTPException(
                status_code=403,
                detail="No workspace context; roles cannot be verified",
            )

        # Resolve get_conn at call-time through the module so tests can patch it.
        import sys
        _mod = sys.modules[__name__]
        with _mod.get_conn() as conn:
            with conn.cursor() as cur:
                if _table_missing(cur, "workspace_member"):
                    raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
                cur.execute(
                    "SELECT role FROM workspace_member "
                    "WHERE workspace_id = %s AND user_id = %s AND status = 'active'",
                    (workspace_id, user_id),
                )
                row = cur.fetchone()
                role = row[0] if row else None

        # Pass if the user's role rank is >= the LOWEST required rank.
        # e.g. require_role("owner", "admin") → min rank is admin(2);
        # an admin(2) satisfies it, a viewer(0) does not.
        if role is None or _ROLE_ORDER.get(role, -1) < min(minimum.values()):
            allowed = ", ".join(sorted(minimum, key=_ROLE_ORDER.get, reverse=True))
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of these roles: {allowed}",
            )
        return user

    return guard


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    expires_at: str
    accepted: bool


@router.get("")
def list_members(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_member"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                SELECT id::text, user_id::text, role, status, created_at
                FROM workspace_member
                WHERE workspace_id = current_setting('kairos.workspace_id', true)::uuid
                ORDER BY created_at
                """
            )
            rows = cur.fetchall()
    return {
        "ok": True,
        "members": [
            {
                "id": r[0], "user_id": r[1], "role": r[2], "status": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ],
    }


@router.get("/invites")
def list_invites(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_invite"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                SELECT id::text, email, role, created_at, expires_at, accepted_at
                FROM workspace_invite
                WHERE workspace_id = current_setting('kairos.workspace_id', true)::uuid
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()
    now = datetime.now(timezone.utc)
    return {
        "ok": True,
        "invites": [
            {
                "id": r[0], "email": r[1], "role": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "expires_at": r[4].isoformat() if r[4] else None,
                "accepted": r[5] is not None,
                "expired": r[4] is not None and r[4] < now,
            }
            for r in rows
        ],
    }


@router.post("/invites", dependencies=[Depends(require_role("owner", "admin"))], status_code=201)
def create_invite(body: InviteCreate, user: dict = Depends(require_user)):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    inviter_id = user.get("id") or user.get("sub")
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_invite"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                INSERT INTO workspace_invite (email, role, invited_by, token, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, email)
                DO UPDATE SET role = EXCLUDED.role, token = EXCLUDED.token,
                              expires_at = EXCLUDED.expires_at, accepted_at = NULL
                RETURNING id::text
                """,
                (body.email, body.role, inviter_id, token, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
    return {"ok": True, "id": row[0], "expires_at": expires_at.isoformat()}


@router.post("/invites/{token}/accept")
def accept_invite(token: str, user: dict = Depends(require_user)):
    user_id = user.get("id") or user.get("sub")
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_invite"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                "SELECT workspace_id::text, role, expires_at, accepted_at FROM workspace_invite WHERE token = %s",
                (token,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Invitation not found")
            workspace_id, role, expires_at, accepted_at = row
            if accepted_at is not None:
                raise HTTPException(status_code=409, detail="Invitation was already accepted")
            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=410, detail="Invitation expired")
            if _table_missing(cur, "workspace_member"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                "SELECT set_config('kairos.workspace_id', %s, true)", (workspace_id,)
            )
            cur.execute(
                """
                INSERT INTO workspace_member (workspace_id, user_id, role, status, invited_by)
                SELECT workspace_id, %s, role, 'active', invited_by
                FROM workspace_invite WHERE token = %s
                ON CONFLICT (workspace_id, user_id)
                DO UPDATE SET role = EXCLUDED.role, status = 'active'
                """,
                (user_id, token),
            )
            cur.execute(
                "UPDATE workspace_invite SET accepted_at = now() WHERE token = %s", (token,)
            )
        conn.commit()
    return {"ok": True, "workspace_id": workspace_id, "role": role}


@router.delete("/invites/{invite_id}", dependencies=[Depends(require_role("owner", "admin"))])
def revoke_invite(invite_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_invite"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                DELETE FROM workspace_invite
                WHERE id = %s::uuid
                  AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                """,
                (invite_id,),
            )
            deleted = cur.rowcount
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return {"ok": True}
