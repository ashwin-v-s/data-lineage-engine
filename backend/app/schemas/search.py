from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SearchResult(BaseModel):
    id: str
    type: str
    name: str
    label: Optional[str] = None  # Display name (fallback to name)
    schema: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    row_count: Optional[int] = None
    steward: Optional[str] = None
    tags: Optional[list[str]] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int