"""
backend/app/api/routes/health.py
─────────────────────────────────
Authenticated readiness probe.

GET /api/v1/health
  - 200  {"status": "ok",       "db": "ok"}         — fully healthy
  - 503  {"status": "degraded", "db": "unavailable"} — DB unreachable

The unauthenticated liveness probe (/healthz) lives in main.py and never
touches the database.  This endpoint is for orchestrators and dashboards that
need to know whether the *full stack* is ready, including the database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(dependencies=[Depends(require_user)])


class HealthResponse(BaseModel):
    status: str
    db: str = "unknown"
    detail: str | None = None


@router.get("/health", response_model=HealthResponse)
def health(response: Response):
    """Return 200/ok when the database is reachable, 503/degraded otherwise."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return HealthResponse(status="ok", db="ok")
    except Exception as exc:
        response.status_code = 503
        return HealthResponse(
            status="degraded",
            db="unavailable",
            detail=str(exc),
        )
