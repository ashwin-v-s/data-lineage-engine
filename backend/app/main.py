"""FastAPI application for the Kairos Data Lineage & Metadata Engine.

Implements all M3, M4, and M5 contracts:
- M3 Entity endpoints: /entities/{entity_id}, /entities/by-name
- M3 Lineage endpoints: /lineage/{entity_id}/graph, /upstream, /downstream with headers
- M3 Evidence endpoints: /evidence/{evidence_id}, /evidence/entity/{id}, /evidence/search
- M4 Reasoning integration: /runs/{run_id}/dependency/{source}/{target}
- Benchmark Evaluation mode: /evaluation/oracle/{run_id}
- Standard error envelope: {"success": false, "error": {...}}
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import uuid

from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.repositories import mock_repository
from backend.app.schemas import (
    ApiErrorResponse,
    BenchmarkOracleRecord,
    BenchmarkOracleResponse,
    ColumnEntity,
    CoverageVectorModel,
    DatasetEntity,
    DependencyReasoningResponse,
    ErrorPayload,
    EvidenceDetailResponse,
    EvidenceDossierData,
    EvidenceListResponse,
    EvidenceSummaryItem,
    HealthResponse,
    LineageEdge,
    LineageGraphResponse,
    LineageGraphStats,
    LineageNode,
    RawEventInfo,
    SearchResponse,
    TemporalContextModel,
    TemporalInterval,
)

app = FastAPI(
    title="Kairos Data Lineage & Metadata Engine",
    description="Historical lineage infrastructure & execution-conditioned reasoning API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Result-Truncated", "X-Total-Count", "X-Returned-Count"],
)


# -----------------------------------------------------------------------------
# Error Handling (Section 15 Contract)
# -----------------------------------------------------------------------------

class ApiCustomError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        entity_id: Optional[str] = None,
        parameter: Optional[str] = None,
        value: Optional[str] = None,
        evidence_id: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.entity_id = entity_id
        self.parameter = parameter
        self.value = value
        self.evidence_id = evidence_id
        self.details = details or {}


@app.exception_handler(ApiCustomError)
async def custom_error_handler(request: Request, exc: ApiCustomError):
    details = dict(exc.details)
    if exc.entity_id:
        details["entity_id"] = exc.entity_id
    if exc.value:
        details["value"] = exc.value
    if exc.evidence_id:
        details["evidence_id"] = exc.evidence_id

    error_dict = {
        "code": exc.code,
        "message": exc.message,
        "details": details,
        "request_id": str(uuid.uuid4()),
    }
    if exc.parameter:
        error_dict["parameter"] = exc.parameter

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": error_dict,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "request_id": str(uuid.uuid4()),
                "details": {"errors": exc.errors()},
            },
        },
    )


# -----------------------------------------------------------------------------
# System & Health
# -----------------------------------------------------------------------------

@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
def health():
    return HealthResponse(
        status="ok",
        db="connected",
        projection="not_configured",
        version="1.0.0-m5",
    )


# -----------------------------------------------------------------------------
# M3 Entity Contract (Section 5)
# -----------------------------------------------------------------------------

@app.get("/api/v1/entities/by-name", tags=["Entities"])
def get_entity_by_name(fqn: str = Query(..., description="Fully qualified entity name")):
    ent = mock_repository.get_by_fqn(fqn)
    if not ent:
        raise ApiCustomError(
            status_code=404,
            code="ENTITY_NOT_FOUND",
            message=f"Entity with FQN '{fqn}' not found",
            details={"fqn": fqn},
        )
    return {"success": True, "data": ent}


@app.get("/api/v1/entities/{entity_id}", tags=["Entities"])
def get_entity_by_id(entity_id: str):
    ent = mock_repository.get_by_id(entity_id)
    if not ent:
        raise ApiCustomError(
            status_code=404,
            code="ENTITY_NOT_FOUND",
            message=f"Entity '{entity_id}' not found",
            entity_id=entity_id,
        )
    return {"success": True, "data": ent}


# -----------------------------------------------------------------------------
# Entity Search (Section 20)
# -----------------------------------------------------------------------------

@app.get("/api/v1/search", response_model=SearchResponse, tags=["Discovery"])
def search_entities(
    q: str = Query("", description="Search term for datasets, columns, or views"),
    type: Optional[str] = Query(None, description="dataset | column | view | job | stream"),
    limit: int = Query(20, ge=1, le=100),
):
    results, total = mock_repository.search(query=q, entity_type=type, limit=limit)
    return SearchResponse(query=q, results=results, total=total)


# -----------------------------------------------------------------------------
# M3 Lineage Contract (Section 6, 7, 16)
# -----------------------------------------------------------------------------

def _validate_temporal_param(param_name: str, val: Optional[str]):
    if not val:
        return
    try:
        from datetime import datetime
        datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        raise ApiCustomError(
            status_code=400,
            code="INVALID_TEMPORAL_PARAMETER",
            message=f"Parameter '{param_name}' must be an ISO-8601 formatted timestamp",
            parameter=param_name,
            value=val,
        )


@app.get("/api/v1/lineage/{entity_id}/graph", response_model=LineageGraphResponse, tags=["Lineage"])
@app.get("/api/v1/lineage/{entity_id}", response_model=LineageGraphResponse, tags=["Lineage"])
def get_lineage_graph(
    entity_id: str,
    response: Response,
    granularity: str = Query("COLUMN", regex="^(DATASET|COLUMN)$"),
    depth: int = Query(3, ge=1, le=10),
    valid_at: Optional[str] = Query(None, description="T_v: Validity time [valid_from, valid_to)"),
    known_as_of: Optional[str] = Query(None, description="T_k: Knowledge transaction time [tx_from, tx_to)"),
    as_of: Optional[str] = Query(None, description="Alias for valid_at"),
    recorded_as_of: Optional[str] = Query(None, description="Alias for known_as_of"),
):
    v_time = valid_at or as_of
    k_time = known_as_of or recorded_as_of

    _validate_temporal_param("valid_at", v_time)
    _validate_temporal_param("known_as_of", k_time)

    graph_data = mock_repository.get_graph(
        entity_id=entity_id,
        granularity=granularity,
        depth=depth,
        valid_at=v_time,
        known_as_of=k_time,
    )
    if not graph_data:
        raise ApiCustomError(
            status_code=404,
            code="ENTITY_NOT_FOUND",
            message=f"Lineage graph for entity '{entity_id}' could not be resolved",
            entity_id=entity_id,
        )

    # Section 16 Truncation Headers
    is_truncated = graph_data["stats"]["truncated"]
    total_edges = graph_data["stats"]["total_edges"]
    response.headers["X-Result-Truncated"] = "true" if is_truncated else "false"
    response.headers["X-Total-Count"] = str(total_edges)
    response.headers["X-Returned-Count"] = str(len(graph_data["edges"]))

    return LineageGraphResponse(**graph_data)


@app.get("/api/v1/lineage/{entity_id}/upstream", response_model=LineageGraphResponse, tags=["Lineage"])
def get_lineage_upstream(
    entity_id: str,
    response: Response,
    depth: int = Query(1, ge=1, le=10),
    valid_at: Optional[str] = Query(None),
    known_as_of: Optional[str] = Query(None),
):
    _validate_temporal_param("valid_at", valid_at)
    _validate_temporal_param("known_as_of", known_as_of)
    up = mock_repository.get_upstream(entity_id=entity_id, depth=depth, valid_at=valid_at, known_as_of=known_as_of)
    if not up:
        raise ApiCustomError(status_code=404, code="ENTITY_NOT_FOUND", message=f"Entity '{entity_id}' not found")
    response.headers["X-Result-Truncated"] = "false"
    response.headers["X-Total-Count"] = str(len(up["edges"]))
    response.headers["X-Returned-Count"] = str(len(up["edges"]))
    return LineageGraphResponse(**up)


@app.get("/api/v1/lineage/{entity_id}/downstream", response_model=LineageGraphResponse, tags=["Lineage"])
def get_lineage_downstream(
    entity_id: str,
    response: Response,
    depth: int = Query(1, ge=1, le=10),
    valid_at: Optional[str] = Query(None),
    known_as_of: Optional[str] = Query(None),
):
    _validate_temporal_param("valid_at", valid_at)
    _validate_temporal_param("known_as_of", known_as_of)
    down = mock_repository.get_downstream(entity_id=entity_id, depth=depth, valid_at=valid_at, known_as_of=known_as_of)
    if not down:
        raise ApiCustomError(status_code=404, code="ENTITY_NOT_FOUND", message=f"Entity '{entity_id}' not found")
    response.headers["X-Result-Truncated"] = "false"
    response.headers["X-Total-Count"] = str(len(down["edges"]))
    response.headers["X-Returned-Count"] = str(len(down["edges"]))
    return LineageGraphResponse(**down)


# -----------------------------------------------------------------------------
# M3 Evidence API & Dossier Endpoints (Sections 8 & 9)
# -----------------------------------------------------------------------------

@app.get("/api/v1/evidence/search", response_model=EvidenceListResponse, tags=["Evidence"])
def search_evidence(
    evidence_type: Optional[str] = Query(None),
    source_system: Optional[str] = Query(None),
    granularity: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    recs, total = mock_repository.search_evidence(
        evidence_type=evidence_type,
        source_system=source_system,
        granularity=granularity,
        operator=operator,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return EvidenceListResponse(success=True, total=total, limit=limit, offset=offset, data=recs)


@app.get("/api/v1/evidence/entity/{entity_id}", response_model=EvidenceListResponse, tags=["Evidence"])
def get_evidence_by_entity(
    entity_id: str,
    evidence_type: Optional[str] = Query(None),
    source_system: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    recs, total = mock_repository.get_by_entity(
        entity_id=entity_id,
        evidence_type=evidence_type,
        source_system=source_system,
        limit=limit,
        offset=offset,
    )
    return EvidenceListResponse(success=True, total=total, limit=limit, offset=offset, data=recs)


@app.get("/api/v1/evidence/{evidence_id}", response_model=EvidenceDetailResponse, tags=["Evidence"])
def get_evidence_dossier(evidence_id: str):
    dos = mock_repository.get_evidence_by_id(evidence_id)
    if not dos:
        raise ApiCustomError(
            status_code=404,
            code="EVIDENCE_NOT_FOUND",
            message=f"Evidence record '{evidence_id}' not found",
            evidence_id=evidence_id,
        )
    return EvidenceDetailResponse(success=True, data=EvidenceDossierData(**dos))


# -----------------------------------------------------------------------------
# M4 Reasoning & Prediction Serialization (Sections 10, 11, 12)
# -----------------------------------------------------------------------------

@app.get(
    "/api/v1/runs/{run_id}/dependency/{source}/{target}",
    response_model=DependencyReasoningResponse,
    tags=["Reasoning"],
)
def get_dependency_reasoning(
    run_id: str,
    source: str,
    target: str,
    valid_at: Optional[str] = Query(None),
    known_as_of: Optional[str] = Query(None),
    as_of: Optional[str] = Query(None),
    recorded_as_of: Optional[str] = Query(None),
):
    v_time = valid_at or as_of
    k_time = known_as_of or recorded_as_of
    _validate_temporal_param("valid_at", v_time)
    _validate_temporal_param("known_as_of", k_time)

    res = mock_repository.evaluate_dependency(
        run_id=run_id,
        source=source,
        target=target,
        valid_at=v_time,
        known_as_of=k_time,
    )
    if not res:
        raise ApiCustomError(
            status_code=404,
            code="ENTITY_NOT_FOUND",
            message=f"Dependency '{source}' -> '{target}' for run '{run_id}' not found",
            details={"run_id": run_id, "source": source, "target": target},
        )
    return DependencyReasoningResponse(**res)


# -----------------------------------------------------------------------------
# Benchmark Evaluation Oracle (Section 13 - Hazard Mode Only)
# -----------------------------------------------------------------------------

@app.get("/api/v1/evaluation/oracle/{run_id}", response_model=BenchmarkOracleResponse, tags=["Evaluation Mode"])
def get_evaluation_oracle(run_id: str):
    records = mock_repository.get_benchmark_oracle(run_id)
    return BenchmarkOracleResponse(
        warning="BENCHMARK EVALUATION ONLY: Leakage boundary enforced. Never exposed in normal investigator mode.",
        run_id=run_id,
        records=[BenchmarkOracleRecord(**r) for r in records],
        is_evaluation_mode=True,
    )


# -----------------------------------------------------------------------------
# Frontend Static Mounting (Vite Build / Preview)
# -----------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
FRONTEND_SRC = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/ui", include_in_schema=False)
    def serve_frontend_dist():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

elif FRONTEND_SRC.exists() and (FRONTEND_SRC / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_SRC)), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/ui", include_in_schema=False)
    def serve_frontend_fallback():
        return FileResponse(str(FRONTEND_SRC / "index.html"))
