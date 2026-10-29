from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.auth import require_user
from backend.app.db import health_check


class HealthResponse(BaseModel):
    status: str
    db: str = "unknown"


router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/health", response_model=HealthResponse)
def health():
    result = health_check()
    return HealthResponse(status="ok", db=result["db"])
