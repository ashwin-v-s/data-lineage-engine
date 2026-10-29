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

from fastapi import APIRouter, Depends, HTTPException, Query
from backend.app.auth import optional_user
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.schemas.lineage import LineageEdge, LineageNode, LineageResponse

router = APIRouter(dependencies=[Depends(optional_user)])

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_asset(cur, asset_id: str) -> dict | None:
    """Resolve dataset or column IDs/names to a dataset graph anchor."""
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
            return {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "schema_name": row.get("schema_name"),
                "database_name": row.get("database_name"),
                "source_system": row.get("source_system"),
            }

        # Catalog search returns column_record IDs. The lineage graph is
        # currently dataset anchored, so resolve a column ID to its dataset.
        cur.execute(
            """
            SELECT d.id::text, d.name, d.asset_type AS type,
                   d.schema_name, d.database_name, d.source_system
            FROM column_record cr
            JOIN dataset d ON d.id = cr.dataset_id
            WHERE cr.id = %s::uuid
            LIMIT 1
            """,
            (asset_id,),
        )
        row = cur.fetchone()
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "schema_name": row.get("schema_name"),
                "database_name": row.get("database_name"),
                "source_system": row.get("source_system"),
            }

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
    if row:
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "schema_name": row.get("schema_name"),
            "database_name": row.get("database_name"),
            "source_system": row.get("source_system"),
        }
    return None


def _walk_lineage(
    cur,
    root_id: str,
    granularity: str,
    depth: int,
    as_of: str,
    recorded_as_of: str,
    direction: str = "both",
) -> tuple[dict[str, dict], list[dict]]:
    """BFS over lineage_edge / edge_temporal_version with bitemporal filters.

    direction:
      "both"       – follow edges in either direction (full neighbourhood).
      "upstream"   – only predecessors (edges whose target is in the frontier).
      "downstream" – only successors   (edges whose source is in the frontier).
    """
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
            # RealDictCursor returns dict-like objects
            nodes[r["id"]] = {
                "id": r["id"],
                "name": r["name"],
                "type": r["type"],
                "schema_name": r.get("schema_name"),
                "database_name": r.get("database_name"),
                "source_system": r.get("source_system"),
            }

        # Restrict traversal to the requested direction
        if direction == "upstream":
            direction_sql = "le.target_id = ANY(%s::uuid[])"
            direction_params: list = [list(frontier)]
        elif direction == "downstream":
            direction_sql = "le.source_id = ANY(%s::uuid[])"
            direction_params = [list(frontier)]
        else:
            direction_sql = "(le.source_id = ANY(%s::uuid[]) OR le.target_id = ANY(%s::uuid[]))"
            direction_params = [list(frontier), list(frontier)]

        # Find edges touching any frontier node, respecting bitemporal filters
        cur.execute(
            f"""
            SELECT DISTINCT
                le.id::text      AS le_id,
                le.source_id::text AS source,
                le.target_id::text AS target,
                le.granularity
            FROM   lineage_edge le
            JOIN   edge_temporal_version etv ON etv.edge_id = le.id
            WHERE  {direction_sql}
              AND  le.granularity = %s
              AND  etv.valid_from        <= %s::timestamptz
              AND  (etv.valid_to         IS NULL OR etv.valid_to        > %s::timestamptz)
              AND  etv.transaction_from  <= %s::timestamptz
              AND  (etv.transaction_to   IS NULL OR etv.transaction_to  > %s::timestamptz)
            """,
            (
                *direction_params,
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
            if direction == "upstream":
                candidates = (src,)
            elif direction == "downstream":
                candidates = (tgt,)
            else:
                candidates = (src, tgt)
            for nid in candidates:
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
            nodes[r["id"]] = {
                "id": r["id"],
                "name": r["name"],
                "type": r["type"],
                "schema_name": r.get("schema_name"),
                "database_name": r.get("database_name"),
                "source_system": r.get("source_system"),
            }

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


@router.get("/lineage/{asset_id}/{direction}", response_model=LineageResponse)
def expand_lineage(
    asset_id: str,
    direction: str,
    as_of: Optional[str] = Query(default=None),
    recorded_as_of: Optional[str] = Query(default=None),
    depth: int = Query(default=1, ge=1, le=10),
    granularity: str = Query(default="DATASET", pattern="^(DATASET|COLUMN)$"),
):
    """Directional lineage expansion used by the UI's Upstream / Downstream arrows.

    GET /api/v1/lineage/{asset_id}/upstream    → predecessors only
    GET /api/v1/lineage/{asset_id}/downstream  → successors only
    """
    if direction not in ("upstream", "downstream"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid direction '{direction}'. Use 'upstream' or 'downstream'.",
        )

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
                direction=direction,
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
