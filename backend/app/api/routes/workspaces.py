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
