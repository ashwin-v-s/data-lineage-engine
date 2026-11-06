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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(dependencies=[Depends(require_user)])


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    created_at: str


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
                "SELECT id::text, workspace_name, owner_id::text, created_at "
                "FROM kairos_workspace "
                "WHERE id = %s::uuid",
                (workspace_id,)
            )
            row = cur.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found or you do not have access to it"
        )
    
    return {
        "ok": True,
        "workspace": {
            "id": row[0],
            "name": row[1] or "My Workspace",
            "owner_id": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
        }
    }


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, user: dict = Depends(require_user)):
    """Return workspace details by UUID.
    
    Only accessible to workspace members (enforced by RLS policy).
    """
    from backend.app import db as _db
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Query the workspace with RLS — will deny if user is not a member
            cur.execute(
                "SELECT id::text, workspace_name, owner_id::text, created_at "
                "FROM kairos_workspace "
                "WHERE id = %s::uuid",
                (workspace_id,)
            )
            row = cur.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found or you do not have access to it"
        )
    
    return {
        "ok": True,
        "workspace": {
            "id": row[0],
            "name": row[1] or "Workspace",
            "owner_id": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
        }
    }
