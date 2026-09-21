import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from contracts.evidence import PredictorInput
from contracts.mocks.loaders import load_case
from research.reasoning.engine import FourStateEngine

app = FastAPI(title="Kairos API", version="0.0.1")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}, "request_id": str(uuid.uuid4())}}


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content=error_body(exc.code, exc.message, exc.details))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=error_body("VALIDATION_ERROR", "Invalid request", {"errors": exc.errors()}))


class HealthResponse(BaseModel):
    status: str


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.get("/api/v1/runs/{run_id}/dependency/{source}/{target}")
def dependency(run_id: str, source: str, target: str):
    """Vertical slice on the MOCK fixture (PLUMBING): real engine, canned evidence."""
    keys, static, runtime = load_case("w03_case_when")
    wanted = [k for k in keys if (k.run_id, k.source_column_id, k.target_column_id) == (run_id, source, target)]
    if not wanted:
        raise ApiError(404, "ENTITY_NOT_FOUND", "Dependency not found in the mock fixture")
    (pred,) = FourStateEngine().infer(PredictorInput(tuple(wanted), tuple(static), tuple(runtime)))
    warnings = ["NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE"] if pred.state.value == "POSSIBLE" else []
    return {"state": pred.state.value, "rule_id": pred.rule_id, "explanation": pred.explanation,
            "evidence_ids": list(pred.evidence_ids), "reasoning_version": pred.reasoning_version,
            "is_mock": True, "warnings": warnings}
