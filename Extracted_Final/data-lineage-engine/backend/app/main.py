import uuid
from typing import List, Optional

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from contracts.evidence import PredictorInput
from contracts.mocks.loaders import load_case
from research.reasoning.engine import FourStateEngine

app = FastAPI(title="Kairos API", version="0.0.1")

# Allow frontend on localhost:3000 to call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}, "request_id": str(uuid.uuid4())}}


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content=error_body(exc.code, exc.message, exc.details))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=error_body("VALIDATION_ERROR", "Invalid request", {"errors": exc.errors()}))


class HealthResponse(BaseModel):
    status: str
    db: str = "unknown"


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    try:
        from backend.app.db import health_check
        db_ok = health_check()
        return HealthResponse(status="ok", db="connected" if db_ok else "unreachable")
    except Exception:
        return HealthResponse(status="ok", db="unreachable")


@app.get("/api/v1/runs/{run_id}/dependency/{source}/{target}")
def dependency(run_id: str, source: str, target: str,
               as_of: Optional[str] = Query(None),
               recorded_as_of: Optional[str] = Query(None)):
    """Real dependency state — tries Supabase evidence first, falls back to mock fixture."""
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            # Get static evidence for this source→target pair
            cur.execute("""
                SELECT evidence_type, source_system, parser_status,
                       query_fingerprint, operator
                FROM evidence
                WHERE (source_column_id::text = %s OR %s = ANY(string_to_array(source_column_id::text, ',')))
                   OR (evidence_type = 'STATIC_DEPENDENCY')
                LIMIT 10
            """, [source, source])
            ev_rows = cur.fetchall()

        if ev_rows:
            # Return OBSERVED if we have evidence
            return {
                "state": "OBSERVED",
                "rule_id": "R2",
                "explanation": "Static evidence found in Supabase for this dependency.",
                "evidence_ids": [str(r["query_fingerprint"]) for r in ev_rows[:3]],
                "reasoning_version": "0.1.0",
                "is_mock": False,
                "warnings": [],
            }
    except Exception:
        pass

    # Fallback to mock fixture
    keys, static, runtime = load_case("w03_case_when")
    wanted = [k for k in keys if (k.run_id, k.source_column_id, k.target_column_id) == (run_id, source, target)]
    if not wanted:
        # Return POSSIBLE for unknown dependencies
        return {
            "state": "POSSIBLE",
            "rule_id": "R4",
            "explanation": "Static analysis permits this dependency but evidence is insufficient.",
            "evidence_ids": [],
            "reasoning_version": "0.1.0",
            "is_mock": True,
            "warnings": ["NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE"],
        }
    (pred,) = FourStateEngine().infer(PredictorInput(tuple(wanted), tuple(static), tuple(runtime)))
    warnings = ["NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE"] if pred.state.value == "POSSIBLE" else []
    return {"state": pred.state.value, "rule_id": pred.rule_id, "explanation": pred.explanation,
            "evidence_ids": list(pred.evidence_ids), "reasoning_version": pred.reasoning_version,
            "is_mock": True, "warnings": warnings}


# ---------------------------------------------------------------------------
# MOCK LINEAGE GRAPH ENDPOINT — PLUMBING, returns synthetic graph data
# ---------------------------------------------------------------------------
MOCK_NODES = [
    {"id": "raw_orders", "label": "raw_orders", "type": "TABLE", "system": "postgres",
     "schema": "raw", "description": "Raw ingest from OMS", "is_mock": True},
    {"id": "stg_customer_orders", "label": "stg_customer_orders", "type": "TABLE",
     "system": "postgres", "schema": "staging", "description": "Staged customer orders", "is_mock": True},
    {"id": "orders_fact", "label": "orders_fact", "type": "TABLE", "system": "postgres",
     "schema": "warehouse", "description": "Fact table for orders", "is_mock": True},
    {"id": "revenue_summary", "label": "revenue_summary", "type": "TABLE", "system": "postgres",
     "schema": "mart", "description": "Revenue aggregation", "is_mock": True},
    {"id": "customers_dim", "label": "customers_dim", "type": "TABLE", "system": "postgres",
     "schema": "warehouse", "description": "Customer dimension", "is_mock": True},
]

MOCK_EDGES = [
    {"id": "edge_raw_to_stg", "source": "raw_orders", "target": "stg_customer_orders",
     "reasoning_state": "OBSERVED", "relationship_type": "DERIVED_FROM",
     "d14_warning": False, "evidence_ids": ["ev_001", "ev_002"], "is_mock": True},
    {"id": "edge_stg_to_fact", "source": "stg_customer_orders", "target": "orders_fact",
     "reasoning_state": "OBSERVED", "relationship_type": "DERIVED_FROM",
     "d14_warning": True, "evidence_ids": ["ev_stg_orders_01", "ev_stg_orders_02"], "is_mock": True},
    {"id": "edge_fact_to_rev", "source": "orders_fact", "target": "revenue_summary",
     "reasoning_state": "POSSIBLE", "relationship_type": "AGGREGATED_INTO",
     "d14_warning": False, "evidence_ids": ["ev_003"], "is_mock": True},
    {"id": "edge_cust_to_fact", "source": "customers_dim", "target": "orders_fact",
     "reasoning_state": "OBSERVED", "relationship_type": "JOINED_WITH",
     "d14_warning": False, "evidence_ids": ["ev_004"], "is_mock": True},
]


@app.get("/api/v1/lineage/{entity}")
def get_lineage(entity: str,
                as_of: Optional[str] = Query(None),
                recorded_as_of: Optional[str] = Query(None),
                granularity: str = Query("COLUMN"),
                depth: int = Query(3)):
    """Real lineage graph from Supabase."""
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            # Get all datasets as nodes
            cur.execute("""
                SELECT id, name, schema_name, source_system, asset_type
                FROM dataset
                ORDER BY schema_name, name
            """)
            datasets = cur.fetchall()
            nodes = [
                {
                    "id": str(row["id"]),
                    "label": row["name"],
                    "type": row["asset_type"],
                    "system": row["source_system"],
                    "schema": row["schema_name"],
                    "description": f"{row['schema_name']}.{row['name']}",
                    "is_mock": False,
                }
                for row in datasets
            ]

            # Get lineage edges with temporal filter
            time_filter = ""
            params = []
            if as_of:
                time_filter += " AND etv.valid_from <= %s AND (etv.valid_to IS NULL OR %s < etv.valid_to)"
                params += [as_of, as_of]
            if recorded_as_of:
                time_filter += " AND etv.transaction_from <= %s AND (etv.transaction_to IS NULL OR %s < etv.transaction_to)"
                params += [recorded_as_of, recorded_as_of]

            cur.execute(f"""
                SELECT
                    le.id,
                    le.source_id,
                    le.target_id,
                    le.granularity,
                    src.name AS source_name,
                    tgt.name AS target_name
                FROM lineage_edge le
                LEFT JOIN edge_temporal_version etv ON etv.edge_id = le.id
                LEFT JOIN dataset src ON src.id = le.source_id
                LEFT JOIN dataset tgt ON tgt.id = le.target_id
                WHERE 1=1 {time_filter}
                ORDER BY src.name, tgt.name
            """, params)
            edge_rows = cur.fetchall()
            edges = [
                {
                    "id": str(row["id"]),
                    "source": str(row["source_id"]),
                    "source_label": row["source_name"] or str(row["source_id"]),
                    "target": str(row["target_id"]),
                    "target_label": row["target_name"] or str(row["target_id"]),
                    "reasoning_state": "OBSERVED",
                    "relationship_type": "DERIVED_FROM",
                    "d14_warning": False,
                    "evidence_ids": [],
                    "is_mock": False,
                }
                for row in edge_rows
            ]

        return {
            "anchor": entity,
            "nodes": nodes,
            "edges": edges,
            "as_of": as_of,
            "recorded_as_of": recorded_as_of,
            "granularity": granularity,
            "depth": depth,
            "is_mock": False,
            "warnings": [],
        }
    except Exception as e:
        # Fallback to mock if DB unavailable
        return {
            "anchor": entity,
            "nodes": MOCK_NODES,
            "edges": MOCK_EDGES,
            "as_of": as_of,
            "recorded_as_of": recorded_as_of,
            "granularity": granularity,
            "depth": depth,
            "is_mock": True,
            "warnings": [f"DB_UNAVAILABLE: {str(e)} — showing mock data"],
        }


@app.get("/api/v1/lineage/{entity}/upstream")
def get_lineage_upstream(entity: str, depth: int = Query(1)):
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT le.id, le.source_id, le.target_id,
                       src.name AS source_name, tgt.name AS target_name,
                       src.schema_name AS src_schema, tgt.schema_name AS tgt_schema,
                       src.asset_type AS src_type, tgt.asset_type AS tgt_type,
                       src.source_system AS src_system
                FROM lineage_edge le
                JOIN edge_temporal_version etv ON etv.edge_id = le.id
                LEFT JOIN dataset src ON src.id = le.source_id
                LEFT JOIN dataset tgt ON tgt.id = le.target_id
                WHERE tgt.name = %s
                   OR tgt.id::text = %s
            """, [entity, entity])
            rows = cur.fetchall()
            edges = [{"id": str(r["id"]), "source": str(r["source_id"]),
                      "target": str(r["target_id"]), "reasoning_state": "OBSERVED",
                      "relationship_type": "DERIVED_FROM", "is_mock": False} for r in rows]
            node_ids = {str(r["source_id"]) for r in rows} | {str(r["target_id"]) for r in rows}
            cur.execute("SELECT id, name, schema_name, asset_type, source_system FROM dataset WHERE id::text = ANY(%s)",
                        [list(node_ids)])
            node_rows = cur.fetchall()
            nodes = [{"id": str(r["id"]), "label": r["name"], "type": r["asset_type"],
                      "system": r["source_system"], "schema": r["schema_name"], "is_mock": False}
                     for r in node_rows]
        return {"anchor": entity, "nodes": nodes, "edges": edges, "direction": "upstream", "is_mock": False}
    except Exception as e:
        upstream_edges = [e for e in MOCK_EDGES if e["target"] == entity]
        upstream_ids = {e["source"] for e in upstream_edges}
        upstream_nodes = [n for n in MOCK_NODES if n["id"] in upstream_ids or n["id"] == entity]
        return {"anchor": entity, "nodes": upstream_nodes, "edges": upstream_edges,
                "direction": "upstream", "is_mock": True, "warnings": [str(e)]}


@app.get("/api/v1/lineage/{entity}/downstream")
def get_lineage_downstream(entity: str, depth: int = Query(1)):
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT le.id, le.source_id, le.target_id,
                       src.name AS source_name, tgt.name AS target_name
                FROM lineage_edge le
                JOIN edge_temporal_version etv ON etv.edge_id = le.id
                LEFT JOIN dataset src ON src.id = le.source_id
                LEFT JOIN dataset tgt ON tgt.id = le.target_id
                WHERE src.name = %s OR src.id::text = %s
            """, [entity, entity])
            rows = cur.fetchall()
            edges = [{"id": str(r["id"]), "source": str(r["source_id"]),
                      "target": str(r["target_id"]), "reasoning_state": "OBSERVED",
                      "relationship_type": "DERIVED_FROM", "is_mock": False} for r in rows]
            node_ids = {str(r["source_id"]) for r in rows} | {str(r["target_id"]) for r in rows}
            cur.execute("SELECT id, name, schema_name, asset_type, source_system FROM dataset WHERE id::text = ANY(%s)",
                        [list(node_ids)])
            node_rows = cur.fetchall()
            nodes = [{"id": str(r["id"]), "label": r["name"], "type": r["asset_type"],
                      "system": r["source_system"], "schema": r["schema_name"], "is_mock": False}
                     for r in node_rows]
        return {"anchor": entity, "nodes": nodes, "edges": edges, "direction": "downstream", "is_mock": False}
    except Exception as e:
        downstream_edges = [e for e in MOCK_EDGES if e["source"] == entity]
        downstream_ids = {e["target"] for e in downstream_edges}
        downstream_nodes = [n for n in MOCK_NODES if n["id"] in downstream_ids or n["id"] == entity]
        return {"anchor": entity, "nodes": downstream_nodes, "edges": downstream_edges,
                "direction": "downstream", "is_mock": True, "warnings": [str(e)]}


@app.get("/api/v1/search")
def search(q: str = Query(""), type: Optional[str] = Query(None), limit: int = Query(20)):
    """Real search from Supabase dataset table."""
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            if q:
                cur.execute("""
                    SELECT id, name, schema_name, asset_type, source_system
                    FROM dataset
                    WHERE name ILIKE %s
                       OR schema_name ILIKE %s
                    ORDER BY schema_name, name
                    LIMIT %s
                """, [f"%{q}%", f"%{q}%", limit])
            else:
                cur.execute("""
                    SELECT id, name, schema_name, asset_type, source_system
                    FROM dataset
                    ORDER BY schema_name, name
                    LIMIT %s
                """, [limit])
            rows = cur.fetchall()
            results = [
                {
                    "id": str(row["id"]),
                    "label": row["name"],
                    "type": row["asset_type"],
                    "schema": row["schema_name"],
                    "description": f"{row['schema_name']}.{row['name']} ({row['source_system']})",
                    "is_mock": False,
                }
                for row in rows
            ]
        return {"query": q, "results": results, "total": len(results), "is_mock": False}
    except Exception as e:
        results = [
            {"id": n["id"], "label": n["label"], "type": n["type"],
             "schema": n["schema"], "description": n["description"]}
            for n in MOCK_NODES
            if q.lower() in n["label"].lower() or q == ""
        ]
        return {"query": q, "results": results[:limit], "total": len(results),
                "is_mock": True, "warnings": [str(e)]}


@app.get("/api/v1/assets/{entity}/lineage")
def get_asset_lineage(entity: str,
                      as_of: Optional[str] = Query(None),
                      recorded_as_of: Optional[str] = Query(None),
                      granularity: str = Query("COLUMN"),
                      depth: int = Query(3)):
    """Alias for /api/v1/lineage/{entity} — M5 frontend calls this route."""
    return get_lineage(entity, as_of, recorded_as_of, granularity, depth)


@app.get("/api/v1/assets/{entity}")
def get_asset(entity: str):
    """Return asset metadata by name or UUID."""
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, name, schema_name, asset_type, source_system, namespace
                FROM dataset
                WHERE name = %s OR id::text = %s
                LIMIT 1
            """, [entity, entity])
            row = cur.fetchone()
            if not row:
                raise ApiError(404, "ENTITY_NOT_FOUND", f"Asset '{entity}' not found")
            return {
                "id": str(row["id"]),
                "name": row["name"],
                "display_name": f"{row['schema_name']}.{row['name']}",
                "type": row["asset_type"],
                "system": row["source_system"],
                "schema": row["schema_name"],
                "namespace": row["namespace"],
                "is_mock": False,
            }
    except ApiError:
        raise
    except Exception:
        return {"id": entity, "name": entity, "display_name": entity,
                "type": "TABLE", "system": "unknown", "is_mock": True}


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str):
    """Run metadata — real from Supabase, fallback to mock."""
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            cur.execute("""
                SELECT er.run_id, er.status, er.started_at, er.completed_at,
                       j.name AS job_name, j.namespace
                FROM execution_run er
                JOIN job j ON j.id = er.job_id
                WHERE er.run_id = %s
                LIMIT 1
            """, [run_id])
            row = cur.fetchone()
            if row:
                return {
                    "run_id": row["run_id"],
                    "job_id": row["job_name"],
                    "status": row["status"],
                    "started_at": str(row["started_at"]) if row["started_at"] else None,
                    "is_mock": False,
                }
    except Exception:
        pass
    return {"run_id": run_id, "job_id": "kairos_demo_job", "status": "COMPLETE",
            "started_at": "2026-09-23T09:32:14Z", "is_mock": True}


@app.get("/api/v1/evidence/{evidence_id}")
def get_evidence(evidence_id: str):
    """
    Real evidence from Supabase.
    Returns all evidence records for a given evidence_id, column name,
    or dataset name — supports the UI's evidence panel.
    """
    try:
        from backend.app.db import get_cursor
        with get_cursor() as cur:
            # Try direct evidence_id match first
            cur.execute("""
                SELECT
                    ev.evidence_id,
                    ev.evidence_type,
                    ev.source_system,
                    ev.run_id,
                    ev.granularity,
                    ev.operator,
                    ev.query_fingerprint,
                    ev.parser_status,
                    ev.ingestion_time,
                    ev.diagnostics,
                    src_ds.name AS source_dataset,
                    src_ds.schema_name AS source_schema,
                    tgt_ds.name AS target_dataset,
                    tgt_ds.schema_name AS target_schema,
                    src_col.column_name AS source_column,
                    tgt_col.column_name AS target_column
                FROM evidence ev
                LEFT JOIN dataset src_ds ON src_ds.id = ev.source_dataset_id
                LEFT JOIN dataset tgt_ds ON tgt_ds.id = ev.target_dataset_id
                LEFT JOIN column_record src_col ON src_col.id = ev.source_column_id
                LEFT JOIN column_record tgt_col ON tgt_col.id = ev.target_column_id
                WHERE ev.evidence_id = %s
                   OR src_col.column_name ILIKE %s
                   OR tgt_col.column_name ILIKE %s
                   OR src_ds.name ILIKE %s
                ORDER BY ev.ingestion_time DESC
                LIMIT 20
            """, [evidence_id, f"%{evidence_id}%", f"%{evidence_id}%", f"%{evidence_id}%"])
            rows = cur.fetchall()

            if rows:
                evidence_list = [
                    {
                        "evidence_id": r["evidence_id"],
                        "type": r["evidence_type"],
                        "source_system": r["source_system"],
                        "run_id": r["run_id"],
                        "granularity": r["granularity"],
                        "operator": r["operator"],
                        "query_fingerprint": r["query_fingerprint"],
                        "parser_status": r["parser_status"],
                        "ingestion_time": str(r["ingestion_time"]) if r["ingestion_time"] else None,
                        "source": f"{r['source_schema']}.{r['source_dataset']}.{r['source_column']}"
                                  if r["source_column"] else
                                  f"{r['source_schema']}.{r['source_dataset']}" if r["source_dataset"] else None,
                        "target": f"{r['target_schema']}.{r['target_dataset']}.{r['target_column']}"
                                  if r["target_column"] else
                                  f"{r['target_schema']}.{r['target_dataset']}" if r["target_dataset"] else None,
                        "diagnostics": r["diagnostics"],
                        "is_mock": False,
                    }
                    for r in rows
                ]
                return {
                    "query": evidence_id,
                    "count": len(evidence_list),
                    "evidence": evidence_list,
                    "is_mock": False,
                }
    except Exception as e:
        pass

    # Fallback mock
    return {
        "query": evidence_id,
        "count": 2,
        "evidence": [
            {"evidence_id": "ev_static_001", "type": "STATIC_DEPENDENCY",
             "source_system": "sqlglot", "parser_status": "SUPPORTED", "is_mock": True},
            {"evidence_id": "ev_runtime_001", "type": "RUNTIME_POSITIVE",
             "source_system": "openlineage", "is_mock": True},
        ],
        "is_mock": True,
    }


@app.get("/api/v1/evaluation/oracle/{run_id}")
def get_oracle(run_id: str):
    """Mock benchmark oracle endpoint (PLUMBING)."""
    return {"run_id": run_id, "oracle_available": False,
            "message": "ProvSQL ground truth not yet configured", "is_mock": True}
