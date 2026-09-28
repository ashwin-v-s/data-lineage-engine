from pydantic import BaseModel


class LineageNode(BaseModel):
    id: str
    name: str
    type: str


class LineageResponse(BaseModel):
    asset_id: str
    nodes: list[LineageNode]
    edges: list[dict]