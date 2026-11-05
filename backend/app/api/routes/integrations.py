"""
backend/app/api/routes/integrations.py
──────────────────────────────────────
Private source connectors exposed to the Integrations view.

Endpoints
─────────
  GET    /api/v1/integrations/github/status                 connector readiness
  GET    /api/v1/integrations/github/connect-url            signed OAuth entry point
  POST   /api/v1/integrations/github/callback               store an installation
  GET    /api/v1/integrations/github/connections            list stored connections
  DELETE /api/v1/integrations/github/connections/{id}       disconnect

Every route requires a verified Supabase session and fails closed (HTTP 503)
while the GitHub App or the token encryption key is unconfigured.  Installation
tokens are only ever persisted as the AES-256-GCM envelope produced by
``token_crypto``; no route logs or returns plaintext tokens or ciphertext.
Enabling the connector is an operational decision (see
docs/GITHUB_REPOSITORY_CONNECTOR.md); these endpoints only act on an already
configured deployment.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app import db
from backend.app.auth import require_user
from backend.app.services import github_app, github_connection_store, token_crypto

router = APIRouter(dependencies=[Depends(require_user)])


class GitHubConnectorStatus(BaseModel):
    configured: bool
    missing_env: list[str]
    token_encryption_configured: bool
    read_only: bool = True
    install_url: str | None = None


class GitHubConnectUrl(BaseModel):
    authorize_url: str
    state: str


class GitHubCallbackRequest(BaseModel):
    code: str
    state: str
    installation_id: Optional[int] = None


class GitHubConnection(BaseModel):
    """A stored connection summary. Never carries token material."""

    id: str
    installation_id: int
    account_login: Optional[str] = None
    account_type: Optional[str] = None
    token_expires_at: Optional[str] = None
    scopes: Optional[str] = None
    permissions: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GitHubConnectionList(BaseModel):
    items: list[GitHubConnection]
    total: int


class GitHubDisconnectResult(BaseModel):
    ok: bool
    connection_id: str
    deleted: int


def _require_configured() -> None:
    """Fail closed while the connector or the encryption key is unavailable."""
    if not github_app.GitHubAppClient.is_configured():
        raise HTTPException(status_code=503, detail="The GitHub connector is not configured")
    if not token_crypto.is_configured():
        raise HTTPException(status_code=503, detail="GitHub token encryption is not configured")


def _caller_workspace_id(user: dict) -> str | None:
    """The workspace bound to the session, or ``None`` when it cannot be resolved.

    The verified workspace is normally set by ``require_user`` in the session
    GUC; a workspace carried on the session user is honoured as a fallback.
    """
    if isinstance(user, dict):
        workspace_id = user.get("workspace_id")
        if workspace_id:
            return str(workspace_id)
    return db._workspace_id.get()


def _resolve_installation(client: github_app.GitHubAppClient, installation_id: Optional[int]) -> tuple[int, dict]:
    """Return ``(installation_id, installation)`` for the callback.

    Without an explicit id the app's single installation is used; an ambiguous
    request is rejected rather than guessing.
    """
    if installation_id is not None:
        resolved_id = int(installation_id)
        return resolved_id, client.resolve_installation(resolved_id)
    installations = client.list_installations()
    if len(installations) != 1:
        raise HTTPException(
            status_code=400,
            detail="Specify installation_id: the app has zero or multiple installations",
        )
    installation = installations[0]
    return int(installation["id"]), installation


@router.get("/integrations/github/status", response_model=GitHubConnectorStatus)
def github_connector_status(user: dict = Depends(require_user)):
    missing = github_app.GitHubAppClient.missing_env_vars()
    slug = (os.getenv(github_app.SLUG_ENV) or "").strip()
    return GitHubConnectorStatus(
        configured=not missing,
        missing_env=missing,
        token_encryption_configured=token_crypto.is_configured(),
        install_url=f"https://github.com/apps/{slug}/installations/new" if slug else None,
    )


@router.get("/integrations/github/connect-url", response_model=GitHubConnectUrl)
def github_connect_url(user: dict = Depends(require_user)):
    """Build the GitHub authorize URL with a state bound to this user/workspace."""
    _require_configured()
    workspace_id = _caller_workspace_id(user)
    if not workspace_id:
        raise HTTPException(status_code=503, detail="Workspace context is not available")
    client = github_app.GitHubAppClient()
    state = token_crypto.sign_state(str(user["id"]), workspace_id)
    authorize_url = f"{client.oauth_base}/login/oauth/authorize?" + urlencode(
        {
            "client_id": client.client_id,
            "redirect_uri": client.callback_url,
            "state": state,
        }
    )
    return GitHubConnectUrl(authorize_url=authorize_url, state=state)


@router.post("/integrations/github/callback", response_model=GitHubConnection)
def github_callback(payload: GitHubCallbackRequest, user: dict = Depends(require_user)):
    """Verify the state, exchange the code, and store the connection encrypted."""
    _require_configured()
    try:
        state = token_crypto.verify_state(payload.state)
    except token_crypto.SignedStateError as exc:
        raise HTTPException(
            status_code=400, detail="The GitHub authorization state is invalid or expired"
        ) from exc
    if state["user_id"] != str(user["id"]):
        raise HTTPException(status_code=403, detail="The authorization state belongs to another user")
    caller_workspace = _caller_workspace_id(user)
    if caller_workspace and state["workspace_id"] != caller_workspace:
        raise HTTPException(
            status_code=403, detail="The authorization state belongs to another workspace"
        )

    client = github_app.GitHubAppClient()
    try:
        user_token = client.exchange_user_code(payload.code)
        installation_id, installation = _resolve_installation(client, payload.installation_id)
    except github_app.GitHubAppError as exc:
        raise HTTPException(status_code=502, detail="GitHub could not complete the connection") from exc

    ciphertext = token_crypto.encrypt_token(user_token)
    account = installation.get("account") or {}
    summary = github_connection_store.upsert_connection(
        user_id=str(user["id"]),
        installation_id=installation_id,
        account_login=account.get("login"),
        account_type=account.get("type"),
        token_ciphertext=ciphertext,
        token_key_version=token_crypto.current_key_version(),
        token_expires_at=None,
        scopes=None,
        permissions=installation.get("permissions"),
    )
    return GitHubConnection(**summary)


@router.get("/integrations/github/connections", response_model=GitHubConnectionList)
def github_list_connections(user: dict = Depends(require_user)):
    """List the workspace's connections. The response is token-free."""
    _require_configured()
    rows = github_connection_store.list_connections()
    items = [GitHubConnection(**row) for row in rows]
    return GitHubConnectionList(items=items, total=len(items))


@router.delete("/integrations/github/connections/{connection_id}", response_model=GitHubDisconnectResult)
def github_disconnect(connection_id: str, user: dict = Depends(require_user)):
    """Disconnect a connection; 404 when it is not in the caller's workspace."""
    _require_configured()
    deleted = github_connection_store.delete_connection(connection_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No such GitHub connection in this workspace")
    return GitHubDisconnectResult(ok=True, connection_id=connection_id, deleted=deleted)
