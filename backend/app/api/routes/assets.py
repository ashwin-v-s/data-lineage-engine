"""
backend/app/api/routes/assets.py
──────────────────────────────────
Asset detail endpoint — fetches a single dataset from Supabase.

Endpoint
────────
  GET /api/v1/assets/{asset_id}
      asset_id can be a UUID or a plain dataset name (case-insensitive)
"""
from __future__ import annotations

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from backend.app.auth import require_user
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.api.routes.membership import require_role
from backend.app.schemas.asset import AssetResponse

router = APIRouter(dependencies=[Depends(require_user)])
remove_asset_role = require_role("owner", "admin")

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Try UUID lookup
            if _UUID_RE.match(asset_id):
                cur.execute(
                    """
                    SELECT id::text,
                           name,
                           asset_type AS type,
                           schema_name || '.' || database_name AS description
                    FROM   dataset
                    WHERE  id = %s::uuid
                    LIMIT  1
                    """,
                    (asset_id,),
                )
                row = cur.fetchone()
                if row:
                    return AssetResponse(**dict(row))

            # 2. Name-based lookup (case-insensitive, most recent)
            cur.execute(
                """
                SELECT id::text,
                       name,
                       asset_type AS type,
                       schema_name || '.' || database_name AS description
                FROM   dataset
                WHERE  lower(name) = lower(%s)
                ORDER  BY created_at DESC
                LIMIT  1
                """,
                (asset_id,),
            )
            row = cur.fetchone()
            if row:
                return AssetResponse(**dict(row))

    raise HTTPException(
        status_code=404,
        detail=f"Asset '{asset_id}' not found.",
    )


@router.delete("/assets/{asset_id}", dependencies=[Depends(remove_asset_role)])
def remove_asset(asset_id: uuid.UUID, user: dict = Depends(require_user)):
    """Hide one asset from active catalog reads while retaining lineage history."""
    actor_id = user.get("id") or user.get("sub")
    if not actor_id:
        raise HTTPException(status_code=401, detail="Authenticated user id is missing")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT asset_id::text AS id, asset_name AS name
                FROM public.kairos_remove_dataset(%s::uuid, %s::uuid)
                """,
                (str(asset_id), str(actor_id)),
            )
            asset = cur.fetchone()
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found in the active catalog")

    return {
        "ok": True,
        "asset_id": str(asset_id),
        "removed": True,
        "message": "Asset removed from the active catalog. Lineage, evidence, and raw events were preserved.",
    }
