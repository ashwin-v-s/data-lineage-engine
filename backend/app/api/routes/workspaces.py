"""
backend/app/api/routes/workspaces.py
────────────────────────────────────
Workspace management: retrieve workspace and member information.

Endpoints
─────────
  GET    /api/v1/me/workspace      the current user's personal workspace
  GET    /api/v1/workspaces/{id}   retrieve workspace details by UUID

Workspace isolation is enforced by row-level security at the database layer
(migration 0007_membership_roles). A user can only see workspaces they are a
member of, and only through this endpoint after authentication.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.services.email_delivery import (
    EmailDeliveryError,
    EmailSettings,
    send_welcome_email,
)

router = APIRouter(dependencies=[Depends(require_user)])

# The workspace registry itself (kairos_workspace) is deliberately unreachable
# from the API role: migration 0003 gives it FORCE ROW LEVEL SECURITY with a
# default-deny policy and no grants. Memberships are read only through this
# SECURITY DEFINER function, which returns the workspaces the supplied verified
# user is an active member of.
_MEMBERSHIP_SELECT = (
    "SELECT workspace_id::text, workspace_name, role, is_current "
    "FROM kairos_list_user_workspaces(%s::uuid) "
)

_NOT_FOUND_DETAIL = "Workspace not found or you do not have access to it"


class WelcomeEmailRequest(BaseModel):
    event_id: uuid.UUID


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    # Null unless the caller's membership role on this workspace is 'owner'.
    owner_id: str | None
    # The registry's created_at is not readable by the API role.
    created_at: str | None


def _workspace_payload(row, user: dict, default_name: str) -> dict:
    """Map one membership row (workspace_id, name, role, is_current) to the API shape."""
    workspace_id, name, role, _is_current = row
    return {
        "id": workspace_id,
        "name": name or default_name,
        "owner_id": user["id"] if role == "owner" else None,
        "created_at": None,
    }


@router.get("/me/workspace")
def get_my_workspace(user: dict = Depends(require_user)):
    """Return the current user's personal workspace.
    
    Each user gets a personal workspace created automatically on signup.
    This endpoint returns that workspace's ID and metadata.
    """
    from backend.app import db as _db
    
    workspace_id = _db._workspace_id.get()
    if not workspace_id:
        raise HTTPException(
            status_code=403,
            detail="No workspace context available; user may not be fully provisioned"
        )
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _MEMBERSHIP_SELECT + "WHERE is_current LIMIT 1",
                (user["id"],)
            )
            row = cur.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    
    return {
        "ok": True,
        "workspace": _workspace_payload(row, user, "My Workspace"),
    }


@router.get("/me/workspaces")
def list_my_workspaces(user: dict = Depends(require_user)):
    """List only workspaces where the verified user has active membership."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM kairos_list_user_workspaces(%s::uuid)", (user["id"],))
            rows = cur.fetchall()
    return {
        "ok": True,
        "workspaces": [
            {"id": str(row[0]), "name": row[1], "role": row[2], "current": bool(row[3])}
            for row in rows
        ],
    }


@router.post("/me/welcome-email")
def send_login_welcome_email(body: WelcomeEmailRequest, user: dict = Depends(require_user)):
    """Send one welcome message per authenticated login session."""
    try:
        settings = EmailSettings.from_env()
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if settings is None:
        raise HTTPException(
            status_code=503,
            detail="Welcome email is not configured on this server.",
        )
    email = str(user.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=422, detail="The authenticated account has no email address")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kairos_welcome_email_delivery
                    (user_id, event_id, recipient_email, delivery_status)
                VALUES (%s::uuid, %s::uuid, %s, 'PENDING')
                ON CONFLICT (workspace_id, user_id, event_id) DO NOTHING
                RETURNING id::text
                """,
                (user["id"], str(body.event_id), email),
            )
            delivery = cur.fetchone()
            if not delivery:
                # Claim a retry only if the previous SMTP attempt definitively
                # failed. PENDING/SENT rows stay idempotent under concurrent
                # requests, while transient provider outages can recover on
                # the next app load with the same login event id.
                cur.execute(
                    """
                    UPDATE kairos_welcome_email_delivery
                    SET delivery_status='PENDING', failure_code=NULL, sent_at=NULL
                    WHERE user_id=%s::uuid AND event_id=%s::uuid
                      AND delivery_status='FAILED'
                    RETURNING id::text
                    """,
                    (user["id"], str(body.event_id)),
                )
                retry = cur.fetchone()
                if retry:
                    delivery = retry
                else:
                    cur.execute(
                        "SELECT delivery_status FROM kairos_welcome_email_delivery WHERE user_id=%s::uuid AND event_id=%s::uuid",
                        (user["id"], str(body.event_id)),
                    )
                    existing = cur.fetchone()
                    status = existing[0] if existing else "UNKNOWN"
                    return {"ok": True, "sent": status == "SENT", "duplicate": True, "delivery_status": status}
            delivery_id = delivery[0]

    metadata = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    display_name = metadata.get("full_name") or metadata.get("name")
    try:
        send_welcome_email(email, str(display_name) if display_name else None)
    except EmailDeliveryError as exc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE kairos_welcome_email_delivery SET delivery_status='FAILED', failure_code=%s WHERE id=%s::uuid",
                    ("SMTP_DELIVERY_FAILED", delivery_id),
                )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE kairos_welcome_email_delivery SET delivery_status='SENT', sent_at=now() WHERE id=%s::uuid",
                (delivery_id,),
            )
    return {"ok": True, "sent": True, "duplicate": False}


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, user: dict = Depends(require_user)):
    """Return workspace details by UUID.
    
    The lookup is restricted to the caller's own active memberships, so a
    foreign workspace id and an id that does not exist are indistinguishable:
    both answer with the same 404.
    """
    try:
        uuid.UUID(str(workspace_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _MEMBERSHIP_SELECT + "WHERE workspace_id = %s::uuid LIMIT 1",
                (user["id"], workspace_id)
            )
            row = cur.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    
    return {
        "ok": True,
        "workspace": _workspace_payload(row, user, "Workspace"),
    }
