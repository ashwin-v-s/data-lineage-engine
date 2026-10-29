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

from fastapi import APIRouter, Depends, Query
from backend.app.auth import require_user
from psycopg2.extras import RealDictCursor

from backend.app.db import get_conn
from backend.app.schemas.search import SearchResponse, SearchResult

router = APIRouter(dependencies=[Depends(require_user)])

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
                    d.database_name || '.' || d.schema_name || '.' || d.name AS name,
                    d.name                                                  AS label,
                    d.schema_name                                           AS schema,
                    NULL::text                                              AS owner,
                    NULL::text                                              AS description,
                    d.created_at                                            AS created,
                    d.created_at                                            AS updated,
                    NULL::int                                               AS row_count,
                    NULL::text                                              AS steward,
                    NULL::text[]                                            AS tags
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
                        || '.' || cr.column_name                                       AS name,
                    cr.column_name                                                     AS label,
                    d.schema_name                                                      AS schema,
                    NULL::text                                                         AS owner,
                    NULL::text                                                         AS description,
                    d.created_at                                                       AS created,
                    d.created_at                                                       AS updated,
                    NULL::int                                                          AS row_count,
                    NULL::text                                                         AS steward,
                    NULL::text[]                                                       AS tags
                FROM column_record cr
                JOIN dataset d ON d.id = cr.dataset_id
                WHERE ( lower(cr.column_name) ILIKE lower(%(pat)s)
                     OR lower(cr.data_type)   ILIKE lower(%(pat)s) )
            """ if not asset_type or asset_type.upper() == "COLUMN" else "SELECT NULL::text, NULL::text, NULL::text, NULL::text, NULL::text, NULL::text, NULL::text, NULL::timestamptz, NULL::timestamptz, NULL::int, NULL::text, NULL::text[] WHERE false"

            # ── Union + count ───────────────────────────────────────────────
            union_sql = f"({dataset_sql}) UNION ALL ({column_sql})"

            count_sql = f"SELECT COUNT(*) AS total FROM ({union_sql}) sub"
            cur.execute(count_sql, {"pat": pattern, "asset_type": asset_type})
            total: int = cur.fetchone()["total"]

            page_sql = f"""
                SELECT id, type, name, label, schema, owner, description, created, updated, row_count, steward, tags
                FROM   ({union_sql}) sub
                ORDER  BY {sort_col} {order}
                LIMIT  %(limit)s OFFSET %(offset)s
            """
            cur.execute(page_sql, {"pat": pattern, "asset_type": asset_type, "limit": page_size, "offset": offset})
            rows = cur.fetchall()

    results = [
        SearchResult(
            id=r["id"],
            type=r["type"],
            name=r["name"],
            label=r["label"],
            schema=r["schema"],
            owner=r["owner"],
            description=r["description"],
            created=r["created"],
            updated=r["updated"],
            row_count=r["row_count"],
            steward=r["steward"],
            tags=r["tags"],
        )
        for r in rows
        if r["id"] is not None
    ]
    return SearchResponse(results=results, total=total)


@router.get("/catalog")
def catalog_snapshot(user: dict = Depends(require_user)):
    """Return catalog records backed by Kairos' PostgreSQL schema."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT d.id::text AS id, d.source_system, d.namespace,
                       d.database_name, d.schema_name, d.name,
                       d.asset_type, d.created_at,
                       COUNT(DISTINCT cr.id)::int AS column_count
                FROM dataset d
                LEFT JOIN column_record cr ON cr.dataset_id = d.id
                GROUP BY d.id
                ORDER BY d.database_name, d.schema_name, d.name
            """)
            assets = [dict(row) for row in cur.fetchall()]
            cur.execute("""
                SELECT le.id::text AS id,
                       le.source_id::text AS source_asset_id,
                       le.target_id::text AS target_asset_id,
                       le.granularity AS edge_type,
                       le.operator_fingerprint,
                       ev.evidence_type AS mapping_type,
                       etv.valid_from, etv.valid_to,
                       etv.transaction_from AS recorded_from
                FROM lineage_edge le
                LEFT JOIN edge_temporal_version etv ON etv.edge_id = le.id
                    AND etv.transaction_to IS NULL
                LEFT JOIN evidence ev ON ev.id = etv.evidence_id
                ORDER BY le.created_at, etv.valid_from
            """)
            edges = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*)::int AS count FROM execution_run")
            run_count = int(cur.fetchone()["count"])
            cur.execute("SELECT COUNT(*)::int AS count FROM evidence")
            evidence_count = int(cur.fetchone()["count"])
            cur.execute("""
                SELECT er.run_id, er.status, er.started_at, er.completed_at, j.name AS job_name
                FROM execution_run er JOIN job j ON j.id = er.job_id
                ORDER BY er.started_at DESC NULLS LAST LIMIT 100
            """)
            runs = [dict(row) for row in cur.fetchall()]
            cur.execute("""
                SELECT e.id::text AS id,
                       e.evidence_id,
                       e.evidence_type,
                       e.source_system,
                       e.run_id,
                       e.granularity,
                       e.operator,
                       e.coverage,
                       e.diagnostics,
                       e.event_time,
                       e.effective_time,
                       sd.database_name || '.' || sd.schema_name || '.' || sd.name AS source_dataset,
                       sc.column_name AS source_column,
                       td.database_name || '.' || td.schema_name || '.' || td.name AS target_dataset,
                       tc.column_name AS target_column,
                       COALESCE((
                           SELECT es.state
                           FROM execution_state es
                           WHERE es.run_id = e.run_id
                             AND es.source_column_id = e.source_column_id
                             AND es.target_column_id = e.target_column_id
                           ORDER BY es.computed_at DESC LIMIT 1
                       ), 'UNKNOWN') AS state
                FROM evidence e
                LEFT JOIN column_record sc ON sc.id = e.source_column_id
                LEFT JOIN dataset sd ON sd.id = COALESCE(sc.dataset_id, e.source_dataset_id)
                LEFT JOIN column_record tc ON tc.id = e.target_column_id
                LEFT JOIN dataset td ON td.id = COALESCE(tc.dataset_id, e.target_dataset_id)
                ORDER BY e.ingestion_time DESC
            """)
            evidence_rows = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*)::int AS count FROM raw_event")
            raw_event_count = int(cur.fetchone()["count"])

    for row in (*assets, *edges):
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()

    evidence = []
    for row in evidence_rows:
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()
        source_name = ".".join(part for part in (row.get("source_dataset"), row.get("source_column")) if part)
        target_name = ".".join(part for part in (row.get("target_dataset"), row.get("target_column")) if part)
        evidence.append({
            "id": row["id"], "source_name": source_name or row.get("source_system") or "Unknown source",
            "target_name": target_name or "Unknown target", "state": row.get("state") or "UNKNOWN",
            "evidence_type": row.get("evidence_type"), "run_id": row.get("run_id"),
            "coverage": row.get("coverage"), "rule_name": row.get("operator") or row.get("granularity"),
            "explanation": (
                row["diagnostics"].get("explanation", "Stored evidence record; inspect its scope and coverage before interpreting it.")
                if isinstance(row.get("diagnostics"), dict)
                else "Stored evidence record; inspect its scope and coverage before interpreting it."
            ),
            "event_time": row.get("event_time"), "effective_time": row.get("effective_time"),
            "metadata": {"source_system": row.get("source_system"), "evidence_id": row.get("evidence_id")},
        })

    return {
        "ok": True,
        "assets": [
            {
                **asset,
                "qualified_name": ".".join(
                    str(part) for part in (
                        asset.get("database_name"), asset.get("schema_name"), asset.get("name")
                    ) if part
                ),
                "owner_name": None,
                "metadata": {"source_system": asset.get("source_system")},
            }
            for asset in assets
        ],
        "edges": edges,
        "evidence": evidence,
        "runs": [
            {
                "id": run.get("run_id"),
                "pipeline_name": run.get("job_name") or run.get("run_id"),
                "status": run.get("status"),
                "started_at": run["started_at"].isoformat() if run.get("started_at") else None,
                "completed_at": run["completed_at"].isoformat() if run.get("completed_at") else None,
                "duration_ms": (
                    int((run["completed_at"] - run["started_at"]).total_seconds() * 1000)
                    if run.get("started_at") and run.get("completed_at") else None
                ),
                "asset_count": 0,
                "event_count": 0,
                "environment_name": None,
            }
            for run in runs
        ],
        "quality_checks": [],
        "column_classifications": [],
        "counts": {
            "assets": len(assets), "edges": len(edges),
            "evidence": evidence_count, "runs": run_count,
            "quality_checks": 0, "raw_events": raw_event_count,
        },
    }


@router.get("/raw-events")
def list_raw_events(
    limit: int = Query(default=25, ge=1, le=100),
    event_id: Optional[str] = Query(default=None, alias="id"),
    user: dict = Depends(require_user),
):
    """Read authenticated immutable source-event metadata or one payload."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if event_id:
                cur.execute("""
                    SELECT event_id, payload, payload_hash, source_system, ingestion_time
                    FROM raw_event WHERE event_id = %s LIMIT 1
                """, (event_id,))
                row = cur.fetchone()
                if not row:
                    return {"ok": False, "message": "Raw event not found"}
                data = dict(row)
                payload = data.pop("payload")
                ingested = data.get("ingestion_time")
                return {"ok": True, "event": {
                    "id": data["event_id"], "source_system": data["source_system"],
                    "payload_hash": data["payload_hash"],
                    "recorded_at": ingested.isoformat() if ingested else None,
                    "payload": payload,
                }}

            cur.execute("""
                SELECT event_id, payload_hash, source_system, ingestion_time,
                       octet_length(payload::text)::int AS payload_bytes,
                       payload->>'event_type' AS event_type,
                       COALESCE(payload->>'event_time', payload->'event'->>'eventTime') AS event_time
                FROM raw_event
                ORDER BY ingestion_time DESC
                LIMIT %s
            """, (limit,))
            rows = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*)::int AS total FROM raw_event")
            total = int(cur.fetchone()["total"])
    events = []
    for row in rows:
        events.append({
            "id": row["event_id"], "source_system": row["source_system"],
            "payload_hash": row["payload_hash"], "payload_bytes": row["payload_bytes"],
            "event_type": row["event_type"] or "Unknown", "event_time": row["event_time"],
            "recorded_at": row["ingestion_time"].isoformat() if row["ingestion_time"] else None,
        })
    return {"ok": True, "events": events, "total": total}
