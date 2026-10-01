"""Pydantic models for the Kairos v1 API contract.

Covers:
- Common & Error shapes ({"success": false, "error": {...}})
- M3 Entity Contract (Dataset & Column entities)
- M3 Lineage Contract (Graph traversal with half-open bitemporal intervals)
- M3 Evidence API & Dossier Endpoints (evidence search, entity evidence, raw_event payload_hash)
- M4 Reasoning Integration (Prediction serialization with fixed UI interpretations)
- Evaluation Oracle (Hazard mode only)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Common Error Shape (Section 15)
# -----------------------------------------------------------------------------

class ErrorPayload(BaseModel):
    code: str = Field(..., description="Stable error code (e.g., ENTITY_NOT_FOUND, INVALID_TEMPORAL_PARAMETER)")
    message: str = Field(..., description="Human-readable explanation of the failure")
    entity_id: Optional[str] = None
    parameter: Optional[str] = None
    value: Optional[str] = None
    evidence_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ErrorPayload


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field("ok", description="ok | degraded | down")
    db: str = Field("connected", description="Storage authority connection status")
    projection: str = Field("not_configured", description="Graph projection status")
    version: str = Field("1.0.0-m5", description="Kairos engine version")


# -----------------------------------------------------------------------------
# M3 Entity Contract (Section 5)
# -----------------------------------------------------------------------------

class DatasetEntity(BaseModel):
    id: str
    type: str = "dataset"
    source_system: str
    namespace: str
    database_name: str
    schema_name: str
    name: str
    asset_type: str
    created_at: str
    display_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ColumnEntity(BaseModel):
    id: str
    type: str = "column"
    dataset_id: str
    column_name: str
    data_type: str
    schema_version: Optional[str] = None
    created_at: str
    display_name: str
    fully_qualified_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EntitySearchItem(BaseModel):
    id: str
    name: str
    type: str  # dataset | column | view | job | stream
    namespace: str
    display_name: str
    fully_qualified_name: Optional[str] = None
    column_count: Optional[int] = None
    row_count: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    results: List[EntitySearchItem]
    total: int
    cursor: Optional[str] = None


# -----------------------------------------------------------------------------
# Bitemporal Semantics (Section 7)
# -----------------------------------------------------------------------------

class TemporalInterval(BaseModel):
    valid_from: str
    valid_to: Optional[str] = None  # None indicates open-ended/current
    transaction_from: str
    transaction_to: Optional[str] = None  # None indicates current belief
    effective_time_status: str = "VERIFIED"  # VERIFIED | ESTIMATED | UNKNOWN
    is_current: bool = True
    is_correction: bool = False
    correction_of: Optional[str] = None


class TemporalContextModel(BaseModel):
    valid_at: Optional[str] = Field(None, description="T_v: Real-world validity time (half-open [valid_from, valid_to))")
    known_as_of: Optional[str] = Field(None, description="T_k: Knowledge transaction time [transaction_from, transaction_to)")


# -----------------------------------------------------------------------------
# M3 Lineage Contract (Section 6)
# -----------------------------------------------------------------------------

class LineageNode(BaseModel):
    id: str
    type: str  # dataset | column | view | job | stream
    name: str
    display_name: str
    namespace: str
    schema_version: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LineageEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    granularity: str = "COLUMN"  # DATASET | COLUMN
    operator_fingerprint: Optional[str] = None
    query_fingerprint: Optional[str] = None
    relationship_type: str = "DERIVED_FROM"  # DERIVED_FROM | READS | WRITES | TRANSFORMS
    reasoning_state: str = "POSSIBLE"  # OBSERVED | REFUTED_FOR_RUN | POSSIBLE | UNKNOWN
    temporal: TemporalInterval
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    d14_warning: bool = False


class LineageGraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    depth: int
    truncated: bool = False


class LineageGraphResponse(BaseModel):
    center_node: LineageNode
    nodes: List[LineageNode]
    edges: List[LineageEdge]
    stats: LineageGraphStats
    temporal: TemporalContextModel
    evidence_information: Dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# M3 Evidence API Contract (Sections 8 & 9)
# -----------------------------------------------------------------------------

class RawEventInfo(BaseModel):
    event_id: str
    payload: Dict[str, Any]
    payload_hash: str  # Hash comes from raw_event per contract
    source_system: str
    ingestion_time: str


class EvidenceDossierData(BaseModel):
    evidence_id: str
    evidence_type: str
    source_system: str
    run_id: Optional[str] = None
    granularity: str
    operator: Optional[str] = None
    query_fingerprint: Optional[str] = None
    schema_fingerprint: Optional[str] = None
    expression_fingerprint: Optional[str] = None
    parser_status: str
    coverage: Dict[str, Any] = Field(default_factory=dict)
    temporal: Dict[str, Any] = Field(default_factory=dict)
    source: Dict[str, Any] = Field(default_factory=dict)
    target: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    raw_event: RawEventInfo
    lineage_versions: List[Dict[str, Any]] = Field(default_factory=list)


class EvidenceDetailResponse(BaseModel):
    success: bool = True
    data: EvidenceDossierData


class EvidenceSummaryItem(BaseModel):
    id: str
    evidence_id: str
    evidence_type: str
    source_system: str
    run_id: Optional[str] = None
    granularity: str
    operator: Optional[str] = None
    event_time: str
    payload_hash: str
    source_column_id: Optional[str] = None
    target_column_id: Optional[str] = None


class EvidenceListResponse(BaseModel):
    success: bool = True
    total: int
    limit: int
    offset: int
    data: List[EvidenceSummaryItem]


# -----------------------------------------------------------------------------
# M4 Reasoning / Prediction Serialization (Section 10, 11, 12)
# -----------------------------------------------------------------------------

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


class DependencyReasoningResponse(BaseModel):
    run_id: str
    source: Dict[str, str]
    target: Dict[str, str]
    granularity: str
    state: str  # OBSERVED | REFUTED_FOR_RUN | POSSIBLE | UNKNOWN
    interpretation: str  # Locked verbatim sentence from Section 12
    explanation: str
    rule_id: str
    reasoning_version: str
    evidence_ids: List[str]
    coverage: Optional[CoverageVectorModel] = None
    flags: List[str] = Field(default_factory=list)
    temporal_context: TemporalContextModel
    warnings: List[str] = Field(default_factory=list)
    is_mock: bool = True


# -----------------------------------------------------------------------------
# Evaluation Oracle (Section 13 - Hazard Mode Only)
# -----------------------------------------------------------------------------

class BenchmarkOracleRecord(BaseModel):
    run_id: str
    source: str
    target: str
    expected_truth_label: str  # PROPAGATED | NOT_PROPAGATED
    inferred_state: str
    matches: bool
    oracle_hash: str


class BenchmarkOracleResponse(BaseModel):
    warning: str = "BENCHMARK EVALUATION ONLY: Leakage boundary enforced. Never exposed in normal investigator mode."
    run_id: str
    records: List[BenchmarkOracleRecord]
    is_evaluation_mode: bool = True
