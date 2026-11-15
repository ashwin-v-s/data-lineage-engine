from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class LineageNode(BaseModel):
    id: str
    name: str
    type: str
    # Extra fields the frontend LineageNode component uses
    display_name: Optional[str] = None    # same as name, kept for compat
    namespace: Optional[str] = None       # schema_name e.g. "raw", "staging"
    schema_version: Optional[str] = None


class LineageEdge(BaseModel):
    edge_id: str          # React Flow needs a unique id per edge
    source: str
    target: str
    granularity: str
    # Rule-derived readback of the evidence stored for this edge. These are
    # labels, not scores: state says what may be claimed, coverage says how
    # much of the relationship the stored evidence spans.
    state: str = "UNKNOWN"
    state_reason: Optional[str] = None
    coverage: str = "NONE"
    coverage_basis: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    run_count: int = 0
    latest_event_time: Optional[str] = None
    coverage_rule_version: Optional[str] = None


class LineageResponse(BaseModel):
    asset_id: str
    nodes: list[LineageNode]
    edges: list[LineageEdge]
