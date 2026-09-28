from pydantic import BaseModel


class SearchResult(BaseModel):
    id: str
    type: str
    name: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int