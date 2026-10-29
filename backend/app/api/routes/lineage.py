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
from backend.app.auth import require_user
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.schemas.lineage import LineageEdge, LineageNode, LineageResponse

router = APIRouter(dependencies=[Depends(require_user)])

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


@router.get("/evidence-at-time")
def evidence_at_time(
    valid_as_of: str = Query(...),
    recorded_as_of: str = Query(...),
    user: dict = Depends(require_user),
):
    """Return evidence whose known bitemporal interval contains both instants."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT e.id::text AS id, e.evidence_id, e.evidence_type,
                       e.run_id, e.granularity, e.operator, e.coverage,
                       e.source_system,
                       sd.database_name || '.' || sd.schema_name || '.' || sd.name AS source_dataset,
                       sc.column_name AS source_column,
                       td.database_name || '.' || td.schema_name || '.' || td.name AS target_dataset,
                       tc.column_name AS target_column,
                       etv.valid_from, etv.valid_to,
                       etv.transaction_from AS recorded_from,
                       etv.transaction_to AS recorded_to,
                       COALESCE((
                           SELECT es.state FROM execution_state es
                           WHERE es.run_id = e.run_id
                             AND es.source_column_id = e.source_column_id
                             AND es.target_column_id = e.target_column_id
                           ORDER BY es.computed_at DESC LIMIT 1
                       ), 'UNKNOWN') AS state
                FROM evidence e
                JOIN lineage_edge le ON (
                    (le.source_id = e.source_column_id AND le.target_id = e.target_column_id AND e.source_column_id IS NOT NULL)
                    OR (le.source_id = e.source_dataset_id AND le.target_id = e.target_dataset_id AND e.source_dataset_id IS NOT NULL)
                )
                JOIN edge_temporal_version etv ON etv.edge_id = le.id AND etv.evidence_id = e.id
                LEFT JOIN column_record sc ON sc.id = e.source_column_id
                LEFT JOIN dataset sd ON sd.id = COALESCE(sc.dataset_id, e.source_dataset_id)
                LEFT JOIN column_record tc ON tc.id = e.target_column_id
                LEFT JOIN dataset td ON td.id = COALESCE(tc.dataset_id, e.target_dataset_id)
                WHERE etv.transaction_from <= %(recorded)s::timestamptz
                  AND (etv.transaction_to IS NULL OR %(recorded)s::timestamptz < etv.transaction_to)
                  AND etv.effective_time_status = 'KNOWN'
                  AND etv.valid_from <= %(valid)s::timestamptz
                  AND (etv.valid_to IS NULL OR %(valid)s::timestamptz < etv.valid_to)
                ORDER BY e.ingestion_time DESC
            """, {"valid": valid_as_of, "recorded": recorded_as_of})
            rows = [dict(row) for row in cur.fetchall()]
            cur.execute("""
                SELECT COUNT(DISTINCT e.id)::int AS count
                FROM evidence e
                JOIN lineage_edge le ON (
                    (le.source_id = e.source_column_id AND le.target_id = e.target_column_id AND e.source_column_id IS NOT NULL)
                    OR (le.source_id = e.source_dataset_id AND le.target_id = e.target_dataset_id AND e.source_dataset_id IS NOT NULL)
                )
                JOIN edge_temporal_version etv ON etv.edge_id = le.id AND etv.evidence_id = e.id
                WHERE etv.transaction_from <= %(recorded)s::timestamptz
                  AND (etv.transaction_to IS NULL OR %(recorded)s::timestamptz < etv.transaction_to)
                  AND etv.effective_time_status = 'UNKNOWN'
            """, {"recorded": recorded_as_of})
            undated_count = int(cur.fetchone()["count"])
    evidence = []
    for row in rows:
        source_name = ".".join(part for part in (row.get("source_dataset"), row.get("source_column")) if part)
        target_name = ".".join(part for part in (row.get("target_dataset"), row.get("target_column")) if part)
        evidence.append({
            "id": row["id"], "source_name": source_name or row.get("source_system") or "Unknown source",
            "target_name": target_name or "Unknown target", "state": row.get("state") or "UNKNOWN",
            "evidence_type": row.get("evidence_type"), "run_id": row.get("run_id"),
            "valid_from": row["valid_from"].isoformat() if row.get("valid_from") else None,
            "valid_to": row["valid_to"].isoformat() if row.get("valid_to") else None,
            "recorded_from": row["recorded_from"].isoformat() if row.get("recorded_from") else None,
            "recorded_to": row["recorded_to"].isoformat() if row.get("recorded_to") else None,
            "coverage": row.get("coverage"), "rule_name": row.get("operator") or row.get("granularity"),
        })
    return {"ok": True, "counts": {"included": len(evidence), "undated_valid_time": undated_count}, "evidence": evidence}


@router.get("/column-lineage")
def get_column_lineage(
    valid_as_of: Optional[str] = Query(default=None),
    recorded_as_of: Optional[str] = Query(default=None),
    user: dict = Depends(require_user),
):
    """Return explicit column relationships backed by stored evidence."""
    ts_as_of = valid_as_of or _now_utc()
    ts_recorded = recorded_as_of or _now_utc()
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT e.id::text AS evidence_id,
                       e.evidence_type,
                       e.evidence_id AS evidence_ref,
                       e.run_id,
                       e.source_column_id::text AS source_column_id,
                       e.target_column_id::text AS target_column_id,
                       sd.database_name || '.' || sd.schema_name || '.' || sd.name AS source_asset,
                       sc.column_name AS source_column,
                       td.database_name || '.' || td.schema_name || '.' || td.name AS target_asset,
                       tc.column_name AS target_column,
                       le.id::text AS edge_id,
                       etv.valid_from,
                       etv.valid_to,
                       etv.transaction_from,
                       etv.transaction_to,
                       e.diagnostics
                FROM evidence e
                JOIN column_record sc ON sc.id = e.source_column_id
                JOIN dataset sd ON sd.id = sc.dataset_id
                JOIN column_record tc ON tc.id = e.target_column_id
                JOIN dataset td ON td.id = tc.dataset_id
                WHERE e.source_column_id IS NOT NULL
                  AND e.target_column_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1
                    FROM lineage_edge le
                    JOIN edge_temporal_version etv
                      ON etv.edge_id = le.id AND etv.evidence_id = e.id
                    WHERE le.source_id = e.source_column_id
                      AND le.target_id = e.target_column_id
                      AND le.granularity = 'COLUMN'
                      AND etv.valid_from <= %(valid)s::timestamptz
                      AND (etv.valid_to IS NULL OR %(valid)s::timestamptz < etv.valid_to)
                      AND etv.transaction_from <= %(recorded)s::timestamptz
                      AND (etv.transaction_to IS NULL OR %(recorded)s::timestamptz < etv.transaction_to)
                  )
                ORDER BY sd.database_name, sd.schema_name, sd.name, sc.column_name
            """, {"valid": ts_as_of, "recorded": ts_recorded})
            rows = [dict(row) for row in cur.fetchall()]
    mappings = []
    for row in rows:
        valid_from = row.get("valid_from")
        transaction_from = row.get("transaction_from")
        mappings.append({
            "source_asset": row["source_asset"],
            "source_column": row["source_column"],
            "target_asset": row["target_asset"],
            "target_column": row["target_column"],
            "source_asset_id": row["source_column_id"],
            "target_asset_id": row["target_column_id"],
            "transformation": row["evidence_type"],
            "mapping_type": row["evidence_type"],
            "evidence_ref": row["evidence_ref"],
            "run_id": row["run_id"],
            "valid_from": valid_from.isoformat() if valid_from else None,
            "recorded_from": transaction_from.isoformat() if transaction_from else None,
            "metadata": row["diagnostics"] or {},
        })
    return {"ok": True, "mappings": mappings, "counts": {"total": len(mappings), "undated_valid_time": 0}}


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
