"""
backend/app/api/routes/lineage.py
──────────────────────────────────
Returns the lineage graph for a given asset (dataset or column).

Endpoint
────────
  GET /api/v1/assets/{asset_id}/lineage
      ?as_of=<ISO-8601>            valid-time filter  (default: now)
      ?recorded_as_of=<ISO-8601>   transaction-time   (default: now)
      ?depth=<int>                 hops to walk       (default: 3, max: 10)
      ?granularity=DATASET|COLUMN  (default: DATASET)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.schemas.lineage import LineageEdge, LineageNode, LineageResponse

router = APIRouter()

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_asset(cur, asset_id: str) -> dict | None:
    """Resolve by UUID or name; return full row including schema_name."""
    if _UUID_RE.match(asset_id):
        cur.execute(
            """
            SELECT id::text, name, asset_type AS type,
                   schema_name, database_name, source_system
            FROM   dataset
            WHERE  id = %s::uuid
            LIMIT  1
            """,
            (asset_id,),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

    cur.execute(
        """
        SELECT id::text, name, asset_type AS type,
               schema_name, database_name, source_system
        FROM   dataset
        WHERE  lower(name) = lower(%s)
        ORDER  BY created_at DESC
        LIMIT  1
        """,
        (asset_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _walk_lineage(
    cur,
    root_id: str,
    granularity: str,
    depth: int,
    as_of: str,
    recorded_as_of: str,
) -> tuple[dict[str, dict], list[dict]]:
    """BFS over lineage_edge / edge_temporal_version with bitemporal filters."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()
    frontier: set[str] = {root_id}

    for _ in range(depth):
        if not frontier:
            break
        next_frontier: set[str] = set()

        # Resolve names for all current frontier nodes
        cur.execute(
            """
            SELECT id::text, name, asset_type AS type,
                   schema_name, database_name, source_system
            FROM   dataset
            WHERE  id = ANY(%s::uuid[])
            """,
            (list(frontier),),
        )
        for r in cur.fetchall():
            nodes[r["id"]] = dict(r)

        # Find edges touching any frontier node, respecting bitemporal filters
        cur.execute(
            """
            SELECT DISTINCT
                le.id::text      AS le_id,
                le.source_id::text AS source,
                le.target_id::text AS target,
                le.granularity
            FROM   lineage_edge le
            JOIN   edge_temporal_version etv ON etv.edge_id = le.id
            WHERE  (le.source_id = ANY(%s::uuid[]) OR le.target_id = ANY(%s::uuid[]))
              AND  le.granularity = %s
              AND  etv.valid_from        <= %s::timestamptz
              AND  (etv.valid_to         IS NULL OR etv.valid_to        > %s::timestamptz)
              AND  etv.transaction_from  <= %s::timestamptz
              AND  (etv.transaction_to   IS NULL OR etv.transaction_to  > %s::timestamptz)
            """,
            (
                list(frontier), list(frontier),
                granularity,
                as_of, as_of,
                recorded_as_of, recorded_as_of,
            ),
        )
        for row in cur.fetchall():
            src, tgt = row["source"], row["target"]
            key = (src, tgt)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({
                    "edge_id": row["le_id"],
                    "source": src,
                    "target": tgt,
                    "granularity": row["granularity"],
                })
            for nid in (src, tgt):
                if nid not in nodes:
                    next_frontier.add(nid)

        frontier = next_frontier

    # Resolve any neighbour nodes not yet fetched
    unresolved = [
        nid for nid in
        {e["source"] for e in edges} | {e["target"] for e in edges}
        if nid not in nodes
    ]
    if unresolved:
        cur.execute(
            """
            SELECT id::text, name, asset_type AS type,
                   schema_name, database_name, source_system
            FROM   dataset
            WHERE  id = ANY(%s::uuid[])
            """,
            (unresolved,),
        )
        for r in cur.fetchall():
            nodes[r["id"]] = dict(r)

    return nodes, edges


@router.get("/assets/{asset_id}/lineage", response_model=LineageResponse)
def get_lineage(
    asset_id: str,
    as_of: Optional[str] = Query(default=None),
    recorded_as_of: Optional[str] = Query(default=None),
    depth: int = Query(default=3, ge=1, le=10),
    granularity: str = Query(default="DATASET", pattern="^(DATASET|COLUMN)$"),
):
    ts_as_of = as_of or _now_utc()
    ts_rec   = recorded_as_of or _now_utc()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            root = _resolve_asset(cur, asset_id)
            if not root:
                raise HTTPException(
                    status_code=404,
                    detail=f"Asset '{asset_id}' not found.",
                )

            nodes_map, edges = _walk_lineage(
                cur,
                root_id=root["id"],
                granularity=granularity,
                depth=depth,
                as_of=ts_as_of,
                recorded_as_of=ts_rec,
            )

    # Ensure root is always present
    if root["id"] not in nodes_map:
        nodes_map[root["id"]] = root

    nodes = [
        LineageNode(
            id=v["id"],
            name=v["name"],
            type=v.get("type", "TABLE").lower(),
            display_name=v["name"],
            namespace=v.get("schema_name", ""),
            schema_version="v1",
        )
        for v in nodes_map.values()
    ]

    lineage_edges = [
        LineageEdge(
            edge_id=e["edge_id"],
            source=e["source"],
            target=e["target"],
            granularity=e["granularity"],
        )
        for e in edges
    ]

    return LineageResponse(asset_id=root["id"], nodes=nodes, edges=lineage_edges)
