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
from typing import Optional

from fastapi import APIRouter, HTTPException
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.schemas.asset import AssetResponse

router = APIRouter()

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
