"""Server-to-server scheduler triggers.

These routes intentionally sit outside the user-authenticated routers. They
require a dedicated secret and fail closed when it is not configured.
"""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Header, HTTPException

from backend.app.services.freshness_runner import run_scheduled_freshness

router = APIRouter(prefix="/internal", tags=["internal"])

_CRON_SECRET_ENV = "KAIROS_CRON_SECRET"


@router.post("/freshness/run")
def run_freshness_schedule(
    x_kairos_cron_secret: str | None = Header(default=None),
):
    """Run due scheduled freshness evaluations.

    The caller is the database scheduler, not a browser. A missing secret
    disables the route rather than making it public.
    """
    configured = os.getenv(_CRON_SECRET_ENV, "").strip()
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="Scheduled freshness is not configured on this deployment.",
        )
    if not x_kairos_cron_secret or not secrets.compare_digest(
        x_kairos_cron_secret, configured
    ):
        raise HTTPException(status_code=401, detail="Scheduler credential is invalid")
    return run_scheduled_freshness()
