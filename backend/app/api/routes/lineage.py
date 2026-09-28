from fastapi import APIRouter,Query

from backend.app.schemas.lineage import LineageResponse

router = APIRouter()


@router.get("/assets/{asset_id}/lineage", response_model=LineageResponse)
def get_lineage(
    asset_id: str,
    as_of: str | None = Query(default=None),
    recorded_as_of: str | None = Query(default=None),
):
    return {
        "asset_id": asset_id,
        "nodes": [],
        "edges": [],
    }