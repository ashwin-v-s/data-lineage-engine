from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class SearchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    name: str
    label: Optional[str] = None  # Display name (fallback to name)
    schema_: Optional[str] = Field(default=None, alias="schema")
    owner: Optional[str] = None
    description: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    row_count: Optional[int] = None
    steward: Optional[str] = None
    tags: Optional[list[str]] = None
    score: Optional[float] = None  # Search relevance score
    match_type: Optional[str] = None  # keyword, semantic, or hybrid

    @property
    def schema(self) -> Optional[str]:
        return self.schema_


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    page: Optional[int] = None
    page_size: Optional[int] = None
    mode: Optional[str] = None  # hybrid, keyword, or semantic
