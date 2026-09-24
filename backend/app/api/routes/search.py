from fastapi import APIRouter, Query

from backend.app.schemas.search import SearchResponse

router = APIRouter()

@router.get("/search", response_model=SearchResponse)
def search(
    q: str | None = Query(default=None, min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="name"),
sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
asset_type: str | None = Query(default=None)
):
    return {
        "results": [],
        "total": 0,
    }