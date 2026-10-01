from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.db import health_check


class HealthResponse(BaseModel):
    status: str
    db: str = "unknown"


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    result = health_check()
    return HealthResponse(status="ok", db=result["db"])
