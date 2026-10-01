from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


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


class LineageResponse(BaseModel):
    asset_id: str
    nodes: list[LineageNode]
    edges: list[LineageEdge]
