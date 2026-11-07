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
import re
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


def _resolve_installation(
    authorized_installations: list[dict], installation_id: Optional[int]
) -> tuple[int, dict]:
    """Select only an installation visible to the authorizing GitHub user."""
    if installation_id is not None:
        resolved_id = int(installation_id)
        for installation in authorized_installations:
            if int(installation.get("id", -1)) == resolved_id:
                return resolved_id, installation
        raise HTTPException(status_code=403, detail="The GitHub user cannot access this app installation")
    installations = authorized_installations
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
        authorized_installations = client.list_user_installations(user_token)
        installation_id, installation = _resolve_installation(authorized_installations, payload.installation_id)
    except github_app.GitHubAppError as exc:
        client.close()
        raise HTTPException(status_code=502, detail="GitHub could not complete the connection") from exc
    except HTTPException:
        client.close()
        raise
    client.close()

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


def _private_repo_context(connection_id: str, owner: str | None = None, repo: str | None = None):
    """Mint a short-lived installation token only after workspace connection lookup."""
    _require_configured()
    connection = github_connection_store.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="No such GitHub connection in this workspace")
    client = github_app.GitHubAppClient()
    try:
        token = client.create_installation_token(connection["installation_id"])
        repositories = client.list_repositories(token.token)
    except github_app.GitHubAppError as exc:
        client.close()
        status = getattr(exc, "status_code", 0)
        code = status if status in {403, 404} else 502
        message = "GitHub access was denied for this installation" if status == 403 else "GitHub could not list this installation's repositories"
        raise HTTPException(status_code=code, detail=message) from exc
    if owner is not None and repo is not None:
        requested = f"{owner}/{repo}".casefold()
        if not any(str(item.get("full_name", "")).casefold() == requested for item in repositories):
            client.close()
            raise HTTPException(status_code=404, detail="Repository is not available to this workspace connection")
    return client, token.token, repositories


def _repo_path_part(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value)) and value not in {".", ".."}


def _github_error(exc: github_app.GitHubAppError) -> HTTPException:
    status = getattr(exc, "status_code", 0)
    if status == 404:
        return HTTPException(status_code=404, detail="The requested repository resource was not found")
    if status == 403:
        return HTTPException(status_code=403, detail="GitHub denied access to the requested resource")
    return HTTPException(status_code=502, detail="GitHub could not return the requested resource")


@router.get("/integrations/github/connections/{connection_id}/repositories")
def github_repositories(connection_id: str, user: dict = Depends(require_user)):
    client, _token, repositories = _private_repo_context(connection_id)
    try:
        items = [{key: repo.get(key) for key in ("id", "full_name", "private", "default_branch", "html_url", "description")} for repo in repositories]
        return {"items": items, "count": len(items)}
    finally:
        client.close()


@router.get("/integrations/github/connections/{connection_id}/repositories/{owner}/{repo}/branches")
def github_repository_branches(connection_id: str, owner: str, repo: str, user: dict = Depends(require_user)):
    if not _repo_path_part(owner) or not _repo_path_part(repo):
        raise HTTPException(status_code=400, detail="Invalid repository owner or name")
    client, token, _ = _private_repo_context(connection_id, owner, repo)
    try:
        branches = client.list_branches(owner, repo, token)
        return {"items": [{"name": item.get("name"), "protected": item.get("protected", False), "commit_sha": (item.get("commit") or {}).get("sha")} for item in branches], "count": len(branches)}
    except github_app.GitHubAppError as exc:
        raise _github_error(exc) from exc
    finally:
        client.close()


@router.get("/integrations/github/connections/{connection_id}/repositories/{owner}/{repo}/tree")
def github_repository_tree(connection_id: str, owner: str, repo: str, ref: str, user: dict = Depends(require_user)):
    if not _repo_path_part(owner) or not _repo_path_part(repo) or not ref.strip() or len(ref) > 256:
        raise HTTPException(status_code=400, detail="Invalid repository, branch, or commit reference")
    client, token, _ = _private_repo_context(connection_id, owner, repo)
    try:
        tree = client.get_tree(owner, repo, ref, installation_token=token, recursive=True)
        items = tree.get("tree", []) if isinstance(tree, dict) else []
        files = [{"path": item.get("path"), "type": item.get("type"), "size": item.get("size"), "sha": item.get("sha")} for item in items[:5000] if isinstance(item, dict)]
        return {"items": files, "count": len(files), "truncated": bool(tree.get("truncated")) or len(items) > 5000, "commit_sha": tree.get("sha")}
    except github_app.GitHubAppError as exc:
        raise _github_error(exc) from exc
    finally:
        client.close()


@router.get("/integrations/github/connections/{connection_id}/repositories/{owner}/{repo}/content")
def github_repository_file(connection_id: str, owner: str, repo: str, ref: str, path: str, user: dict = Depends(require_user)):
    if not _repo_path_part(owner) or not _repo_path_part(repo) or not ref.strip() or len(ref) > 256 or not path.strip() or len(path) > 1024 or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid repository, branch, or file path")
    client, token, _ = _private_repo_context(connection_id, owner, repo)
    try:
        tree = client.get_tree(owner, repo, ref, installation_token=token, recursive=True)
        items = tree.get("tree", []) if isinstance(tree, dict) else []
        if tree.get("truncated") and not any(item.get("path") == path and item.get("type") == "blob" for item in items if isinstance(item, dict)):
            raise HTTPException(status_code=409, detail="Repository tree was truncated; content path cannot be verified")
        if not any(item.get("path") == path and item.get("type") == "blob" for item in items if isinstance(item, dict)):
            raise HTTPException(status_code=404, detail="File is not present on this repository ref")
        content = client.get_file_content(owner, repo, path, ref, installation_token=token)
        if content.get("unsupported"):
            raise HTTPException(status_code=415, detail="GitHub file is binary, too large, or cannot be decoded as UTF-8")
        return content
    except HTTPException:
        raise
    except github_app.GitHubAppError as exc:
        raise _github_error(exc) from exc
    finally:
        client.close()
