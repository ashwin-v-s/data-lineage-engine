from fastapi import APIRouter

from backend.app.schemas.asset import AssetResponse

router = APIRouter()


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str):
    return {
        "id": asset_id,
        "name": "sample_asset",
        "type": "dataset",
        "description": "Sample KAIROS asset",
    }