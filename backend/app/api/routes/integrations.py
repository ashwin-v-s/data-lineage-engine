"""
backend/app/api/routes/integrations.py
──────────────────────────────────────
Read-only status for external source connectors.

Endpoint
────────
  GET /api/v1/integrations/github/status

Reports whether the private read-only GitHub App connector and the token
encryption key are configured.  It performs no network call and writes nothing,
so it is safe to poll from the Integrations view.  Enabling the connector is an
operational decision (see docs/GITHUB_REPOSITORY_CONNECTOR.md); this endpoint
only makes the current configuration observable instead of silently absent.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth import require_user
from backend.app.services import github_app, token_crypto

router = APIRouter(dependencies=[Depends(require_user)])


class GitHubConnectorStatus(BaseModel):
    configured: bool
    missing_env: list[str]
    token_encryption_configured: bool
    read_only: bool = True
    install_url: str | None = None


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
