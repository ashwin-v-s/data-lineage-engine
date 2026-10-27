"""Generic, source-neutral metadata preview API."""
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from backend.app.services.metadata_normalizer import normalize_json_records

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


@router.post("/preview")
def preview_metadata(
    payload: Any = Body(...),
    source_name: str = Query(default="json_import", max_length=120),
):
    """Preview arbitrary JSON metadata without persisting it or inferring relationships."""
    try:
        return normalize_json_records(payload, source_name=source_name)
    except ValueError as exc:
        return JSONResponse(status_code=413, content={
            "error": {
                "code": "METADATA_PREVIEW_LIMIT_EXCEEDED",
                "message": str(exc),
                "details": {"max_records": 1000},
                "request_id": "metadata-preview",
            }
        })
