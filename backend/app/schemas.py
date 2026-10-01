"""Pydantic schemas for the Kairos v1 API contract (Section 17).

Every public route uses these typed request and response schemas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Common & Error Shapes (Locked Contract)
# -----------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable error code string")
    message: str = Field(..., description="Human-readable error explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic payload")
    request_id: str = Field(..., description="Unique UUID for request tracing")


class ApiErrorEnvelope(BaseModel):
    error: ErrorDetail


class TemporalContextModel(BaseModel):
    as_of: Optional[str] = Field(None, description="Valid time (T_v) ISO-8601 string, or null for latest")
    recorded_as_of: Optional[str] = Field(None, description="Transaction time (T_k) ISO-8601 string, or null for latest")


# -----------------------------------------------------------------------------
# Health Check (Route: GET /api/v1/health)
# -----------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field("ok", description="Overall service status (ok | degraded | down)")
    db: str = Field("connected", description="Database or mock storage health")
    projection: str = Field("not_configured", description="Graph projection status")
    version: str = Field("1.0.0-m5-slice", description="API version")


# -----------------------------------------------------------------------------
# Search (Route: GET /api/v1/search)
# -----------------------------------------------------------------------------

class EntitySummary(BaseModel):
    id: str = Field(..., description="Canonical UUID or qualified identifier")
    name: str = Field(..., description="Entity name or column identifier")
    entity_type: str = Field(..., description="TABLE | VIEW | JOB | COLUMN | STREAM")
    namespace: str = Field(..., description="System or schema namespace")
    description: Optional[str] = None
    column_count: Optional[int] = None
    row_count: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    results: List[EntitySummary]
    total: int
    cursor: Optional[str] = None


# -----------------------------------------------------------------------------
# Lineage Graph (Routes: GET /api/v1/lineage/{entity}, upstream, downstream)
# -----------------------------------------------------------------------------

class LineageNode(BaseModel):
    id: str
    name: str
    entity_type: str
    namespace: str
    schema_version: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LineageEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relationship_type: str = Field("DERIVED_FROM", description="DERIVED_FROM | READS | WRITES | TRANSFORMS")
    granularity: str = Field("COLUMN", description="DATASET | COLUMN")
    reasoning_state: str = Field("POSSIBLE", description="OBSERVED | REFUTED_FOR_RUN | POSSIBLE | UNKNOWN")
    operator: Optional[str] = None
    d14_warning: bool = Field(False, description="True if effective time window is unknown (Decision D-14)")
    temporal_range: Dict[str, Optional[str]] = Field(default_factory=dict)


class LineageResponse(BaseModel):
    anchor_entity_id: str
    nodes: List[LineageNode]
    edges: List[LineageEdge]
    temporal_context: TemporalContextModel
    granularity: str
    depth: int
    truncated: bool = Field(False, description="True if traversal was clipped by depth or node limits")


# -----------------------------------------------------------------------------
# Dependency Reasoning (Route: GET /api/v1/runs/{run_id}/dependency/{source}/{target})
# -----------------------------------------------------------------------------

class EndpointRef(BaseModel):
    column_id: str
    display: str


class CoverageVectorModel(BaseModel):
    run_covered: bool
    operator_covered: bool
    source_dataset_covered: bool
    target_dataset_covered: bool
    source_columns_covered: List[str]
    target_columns_covered: List[str]
    branches_covered: bool
    coverage_mode: str
    parser_status: str


class EvidenceRef(BaseModel):
    evidence_id: str
    type: str
    source_system: str
    event_time: Optional[str] = None
    raw_payload_hash: Optional[str] = None


class ReasoningMeta(BaseModel):
    engine_version: str
    rule_id: str


class DependencyResponse(BaseModel):
    run_id: str
    source: EndpointRef
    target: EndpointRef
    granularity: str
    state: str = Field(..., description="OBSERVED | REFUTED_FOR_RUN | POSSIBLE | UNKNOWN")
    interpretation: str = Field(..., description="Mandatory verbatim 4-state sentence from Section 19")
    temporal_context: TemporalContextModel
    coverage: CoverageVectorModel
    evidence: List[EvidenceRef]
    reasoning: ReasoningMeta
    warnings: List[str] = Field(default_factory=list)
    is_mock: bool = Field(True, description="True if derived from plumbing mock data")


# -----------------------------------------------------------------------------
# Runs & Evidence (Routes: /runs/{run_id}, /evidence/{dependency})
# -----------------------------------------------------------------------------

class RunResponse(BaseModel):
    run_id: str
    job_name: str
    namespace: str
    started_at: str
    completed_at: Optional[str] = None
    status: str
    event_count: int


class RunLineageItem(BaseModel):
    source: str
    target: str
    state: str
    rule_id: str
    evidence_count: int


class RunLineageResponse(BaseModel):
    run_id: str
    dependencies: List[RunLineageItem]
    total: int


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    source_system: str
    event_time: str
    payload_hash: str
    details: Dict[str, Any] = Field(default_factory=dict)


class EvidenceListResponse(BaseModel):
    dependency: str
    records: List[EvidenceItem]
    total: int


# -----------------------------------------------------------------------------
# Ingestion (Routes: POST /api/v1/ingest/openlineage, /api/v1/ingest/sql)
# -----------------------------------------------------------------------------

class OpenLineageIngestRequest(BaseModel):
    eventType: str
    eventTime: str
    run: Dict[str, Any]
    job: Dict[str, Any]
    inputs: List[Dict[str, Any]] = Field(default_factory=list)
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    producer: Optional[str] = None


class SqlIngestRequest(BaseModel):
    sql: str
    schema_snapshot: Dict[str, Any]
    dialect: str = "postgres"
    source_system: str = "manual_sql"


class IngestResponse(BaseModel):
    accepted: bool
    duplicate: bool
    event_id: str
    records_processed: int
    diagnostics: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Benchmark Evaluation Mode (Route: GET /api/v1/evaluation/oracle/{run_id})
# -----------------------------------------------------------------------------

class BenchmarkOracleRecord(BaseModel):
    run_id: str
    source: str
    target: str
    expected_truth_label: str = Field(..., description="PROPAGATED | NOT_PROPAGATED")
    inferred_state: str
    matches: bool
    oracle_hash: str


class BenchmarkOracleResponse(BaseModel):
    warning: str = "EVALUATION ONLY: Strict leakage barrier active."
    run_id: str
    records: List[BenchmarkOracleRecord]
    is_evaluation_mode: bool = True
