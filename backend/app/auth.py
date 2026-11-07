"""Supabase access-token verification for protected Kairos API routes."""
from __future__ import annotations

import os
from typing import Any, AsyncGenerator

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def supabase_auth_url() -> str | None:
    return (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").rstrip("/") or None


def auth_disabled() -> bool:
    """Authentication is mandatory for all API routes, including local runs."""
    return False


async def require_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AsyncGenerator[dict[str, Any], None]:
    """Validate a Supabase token with Auth, including legacy HS256 projects."""
    # FAIL FAST ON MISSING CREDENTIALS before checking infrastructure
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in is required")
    
    url = supabase_auth_url()
    if not url:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    headers = {"Authorization": f"Bearer {credentials.credentials}"}
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
    if key:
        headers["apikey"] = key
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/auth/v1/user", headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Authentication service is unavailable") from exc
    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="Authentication service could not verify the session")
    try:
        user = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Authentication service returned an invalid response") from exc
    if not isinstance(user, dict) or not isinstance(user.get("id"), str):
        raise HTTPException(status_code=401, detail="Session did not identify a user")
    # Provision only from the user UUID returned by Supabase's verified /user
    # endpoint.  Never trust a client-supplied workspace or user identifier.
    try:
        from backend.app.db import provision_personal_workspace, set_workspace_id, reset_workspace_id, get_conn

        workspace_id = provision_personal_workspace(user["id"])
    except Exception as exc:
        # Usually this means migration 0003 has not been applied, or the DB
        # login has not been granted membership in kairos_app.  Fail closed.
        raise HTTPException(
            status_code=503,
            detail="Workspace service is not ready. Apply the workspace migration and try again.",
        ) from exc
    selected_workspace = request.headers.get("x-kairos-workspace-id", "").strip()
    if selected_workspace:
        import uuid
        try:
            selected_workspace = str(uuid.UUID(selected_workspace))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Workspace id is invalid") from exc
        workspace_id = selected_workspace

    token = set_workspace_id(workspace_id)
    try:
        if selected_workspace:
            # The requested workspace id is only a candidate scope. The
            # membership lookup runs under kairos_app RLS scoped to that id;
            # callers cannot read it unless this verified user is active there.
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM workspace_member WHERE user_id=%s::uuid AND status='active' LIMIT 1",
                        (user["id"],),
                    )
                    if cur.fetchone() is None:
                        raise HTTPException(status_code=403, detail="You are not an active member of this workspace")
        yield user
    finally:
        reset_workspace_id(token)


async def optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Backward-compatible alias that now always requires a valid user."""
    async for user in require_user(request, credentials):
        return user
    return None
