"""
backend/app/api/routes/personalization.py
─────────────────────────────────────────
Per-user personalization: recently viewed assets and starred assets.

Endpoints
─────────
  GET    /api/v1/me/recently-viewed?limit=10      most recently opened assets
  POST   /api/v1/me/recently-viewed/{asset_id}    record an asset open
  DELETE /api/v1/me/recently-viewed               clear the caller's history
  POST   /api/v1/assets/{asset_id}/star           star an asset for the caller
  DELETE /api/v1/assets/{asset_id}/star           unstar it
  GET    /api/v1/me/starred-assets                the caller's starred assets

These records are stored per workspace *and* per user, so they are private to
the signed-in Supabase user and never shared between workspaces.  Only the
restricted ``kairos_app`` database login may read or write them (migration
``0005_personalization.sql``).
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(dependencies=[Depends(require_user)])

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)

_ASSET_COLUMNS = """
    d.id::text                              AS asset_id,
    d.name                                  AS name,
    d.asset_type                            AS asset_type,
    d.schema_name                           AS schema_name,
    d.database_name                         AS database_name,
    d.source_system                         AS source_system,
    d.database_name || '.' || d.schema_name || '.' || d.name AS qualified_name
"""


class PersonalizedAsset(BaseModel):
    asset_id: str
    name: str
    asset_type: Optional[str] = None
    schema_name: Optional[str] = None
    database_name: Optional[str] = None
    source_system: Optional[str] = None
    qualified_name: Optional[str] = None
    recorded_at: Optional[str] = None


class PersonalizedAssetList(BaseModel):
    items: list[PersonalizedAsset]
    total: int


class MutationResult(BaseModel):
    ok: bool
    asset_id: Optional[str] = None
    starred: Optional[bool] = None
    deleted: Optional[int] = None


def _resolve_dataset_id(cur, asset_id: str) -> str | None:
    """Resolve an asset UUID or dataset name to a workspace-scoped dataset id."""
    if _UUID_RE.match(asset_id):
        cur.execute("SELECT id::text FROM dataset WHERE id = %s::uuid LIMIT 1", (asset_id,))
        row = cur.fetchone()
        if row:
            return row["id"]
    cur.execute(
        """
        SELECT id::text FROM dataset
        WHERE lower(name) = lower(%s)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (asset_id,),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _require_dataset_id(cur, asset_id: str) -> str:
    resolved = _resolve_dataset_id(cur, asset_id)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return resolved


def _serialize(rows) -> list[PersonalizedAsset]:
    items: list[PersonalizedAsset] = []
    for row in rows:
        data = dict(row)
        recorded = data.pop("recorded_at", None)
        items.append(
            PersonalizedAsset(
                **data,
                recorded_at=recorded.isoformat() if recorded is not None else None,
            )
        )
    return items


@router.get("/me/recently-viewed", response_model=PersonalizedAssetList)
def list_recently_viewed(
    limit: int = Query(default=10, ge=1, le=50),
    user: dict = Depends(require_user),
):
    """Return the caller's most recently opened assets, newest first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ASSET_COLUMNS}, av.viewed_at AS recorded_at
                FROM   asset_view av
                JOIN   dataset d ON d.id = av.asset_id
                WHERE  av.user_id = %s::uuid
                ORDER  BY av.viewed_at DESC
                LIMIT  %s
                """,
                (user["id"], limit),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*)::int AS total FROM asset_view WHERE user_id = %s::uuid",
                (user["id"],),
            )
            total = int(cur.fetchone()["total"])
    return PersonalizedAssetList(items=_serialize(rows), total=total)


@router.post("/me/recently-viewed/{asset_id}", response_model=MutationResult)
def record_asset_view(asset_id: str, user: dict = Depends(require_user)):
    """Record that the caller opened an asset. Idempotent per (user, asset)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            dataset_id = _require_dataset_id(cur, asset_id)
            cur.execute(
                """
                INSERT INTO asset_view (user_id, asset_id, viewed_at)
                VALUES (%s::uuid, %s::uuid, now())
                ON CONFLICT (workspace_id, user_id, asset_id)
                DO UPDATE SET viewed_at = now()
                """,
                (user["id"], dataset_id),
            )
    return MutationResult(ok=True, asset_id=dataset_id)


@router.delete("/me/recently-viewed", response_model=MutationResult)
def clear_recently_viewed(user: dict = Depends(require_user)):
    """Clear the caller's recently viewed history."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM asset_view WHERE user_id = %s::uuid", (user["id"],))
            deleted = cur.rowcount
    return MutationResult(ok=True, deleted=int(deleted or 0))


@router.post("/assets/{asset_id}/star", response_model=MutationResult)
def star_asset(asset_id: str, user: dict = Depends(require_user)):
    """Star an asset for the caller. Idempotent."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            dataset_id = _require_dataset_id(cur, asset_id)
            cur.execute(
                """
                INSERT INTO asset_star (user_id, asset_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT (workspace_id, user_id, asset_id) DO NOTHING
                """,
                (user["id"], dataset_id),
            )
    return MutationResult(ok=True, asset_id=dataset_id, starred=True)


@router.delete("/assets/{asset_id}/star", response_model=MutationResult)
def unstar_asset(asset_id: str, user: dict = Depends(require_user)):
    """Remove the caller's star from an asset. Idempotent."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            dataset_id = _resolve_dataset_id(cur, asset_id)
            if dataset_id is None:
                # Nothing to unstar for an asset that does not exist here.
                return MutationResult(ok=True, asset_id=None, starred=False)
            cur.execute(
                """
                DELETE FROM asset_star
                WHERE user_id = %s::uuid AND asset_id = %s::uuid
                """,
                (user["id"], dataset_id),
            )
    return MutationResult(ok=True, asset_id=dataset_id, starred=False)


@router.get("/me/starred-assets", response_model=PersonalizedAssetList)
def list_starred_assets(user: dict = Depends(require_user)):
    """Return the caller's starred assets, most recently starred first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ASSET_COLUMNS}, s.created_at AS recorded_at
                FROM   asset_star s
                JOIN   dataset d ON d.id = s.asset_id
                WHERE  s.user_id = %s::uuid
                ORDER  BY s.created_at DESC
                """,
                (user["id"],),
            )
            rows = cur.fetchall()
    return PersonalizedAssetList(items=_serialize(rows), total=len(rows))
