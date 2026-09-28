from fastapi import Request
from fastapi.responses import JSONResponse
import uuid


def api_error(
    request: Request,
    message: str,
    status_code: int,
    code: str,
):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )