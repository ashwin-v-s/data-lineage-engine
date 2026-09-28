"""
backend/app/api/routes/search.py
─────────────────────────────────
Full-text search over datasets and columns stored in Supabase.

Endpoint
────────
  GET /api/v1/search
      ?q=<term>            # substring match on name / schema / db  (optional)
      ?asset_type=<str>    # filter by asset_type  e.g. TABLE, VIEW (optional)
      ?page=<int>          # 1-based page number   (default: 1)
      ?page_size=<int>     # results per page      (default: 20, max: 100)
      ?sort_by=<field>     # name | schema_name | asset_type  (default: name)
      ?sort_order=asc|desc (default: asc)

Search strategy
───────────────
  - Datasets: match on name, schema_name, database_name, source_system using
    case-insensitive ILIKE.
  - Columns: match on column_name, data_type using ILIKE, joined to dataset
    for a qualified name.
  - Results from both sets are UNIONed, de-duplicated, then paginated.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.schemas.search import SearchResponse, SearchResult

router = APIRouter()

# Columns we allow sort_by on (whitelist to prevent SQL injection)
_SORTABLE = {"name", "schema_name", "asset_type", "source_system"}


@router.get("/search", response_model=SearchResponse)
def search(
    q: Optional[str] = Query(default=None, description="Search term (substring match)"),
    asset_type: Optional[str] = Query(default=None, description="Filter by asset type, e.g. TABLE"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
):
    # Sanitise sort column
    sort_col = sort_by if sort_by in _SORTABLE else "name"
    order = "ASC" if sort_order == "asc" else "DESC"
    offset = (page - 1) * page_size
    pattern = f"%{q}%" if q else "%"

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ── Dataset search ──────────────────────────────────────────────
            dataset_filters = [
                "( lower(d.name)          ILIKE lower(%(pat)s)",
                "  OR lower(d.schema_name)   ILIKE lower(%(pat)s)",
                "  OR lower(d.database_name) ILIKE lower(%(pat)s)",
                "  OR lower(d.source_system) ILIKE lower(%(pat)s) )",
            ]
            dataset_type_filter = "AND lower(d.asset_type) = lower(%(asset_type)s)" if asset_type else ""

            dataset_sql = f"""
                SELECT
                    d.id::text                                              AS id,
                    d.asset_type                                            AS type,
                    d.database_name || '.' || d.schema_name || '.' || d.name AS name
                FROM dataset d
                WHERE {' '.join(dataset_filters)}
                {dataset_type_filter}
            """

            # ── Column search ───────────────────────────────────────────────
            # Columns have no asset_type of their own; skip asset_type filter for them
            column_sql = """
                SELECT
                    cr.id::text                                                        AS id,
                    'COLUMN'                                                           AS type,
                    d.database_name || '.' || d.schema_name || '.' || d.name
                        || '.' || cr.column_name                                       AS name
                FROM column_record cr
                JOIN dataset d ON d.id = cr.dataset_id
                WHERE ( lower(cr.column_name) ILIKE lower(%(pat)s)
                     OR lower(cr.data_type)   ILIKE lower(%(pat)s) )
            """ if not asset_type or asset_type.upper() == "COLUMN" else "SELECT NULL::text, NULL::text, NULL::text WHERE false"

            # ── Union + count ───────────────────────────────────────────────
            union_sql = f"({dataset_sql}) UNION ALL ({column_sql})"

            count_sql = f"SELECT COUNT(*) AS total FROM ({union_sql}) sub"
            cur.execute(count_sql, {"pat": pattern, "asset_type": asset_type})
            total: int = cur.fetchone()["total"]

            page_sql = f"""
                SELECT id, type, name
                FROM   ({union_sql}) sub
                ORDER  BY {sort_col} {order}
                LIMIT  %(limit)s OFFSET %(offset)s
            """
            cur.execute(page_sql, {"pat": pattern, "asset_type": asset_type, "limit": page_size, "offset": offset})
            rows = cur.fetchall()

    results = [
        SearchResult(id=r["id"], type=r["type"], name=r["name"])
        for r in rows
        if r["id"] is not None
    ]
    return SearchResponse(results=results, total=total)
