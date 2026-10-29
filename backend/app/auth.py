"""Supabase access-token verification for protected Kairos API routes."""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def supabase_auth_url() -> str | None:
    return (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").rstrip("/") or None


def auth_disabled() -> bool:
    """Authentication is mandatory for all API routes, including local runs."""
    return False


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """Validate a Supabase token with Auth, including legacy HS256 projects."""
    url = supabase_auth_url()
    if not url:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in is required")
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
    return user


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Backward-compatible alias that now always requires a valid user."""
    return await require_user(credentials)
