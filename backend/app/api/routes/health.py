from fastapi import APIRouter
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")
