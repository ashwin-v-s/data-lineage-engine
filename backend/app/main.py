from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uuid

from backend.app.api.errors import api_error
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.search import router as search_router
from backend.app.api.routes.assets import router as assets_router
from backend.app.api.routes.lineage import router as lineage_router
from backend.app.api.routes.dependency import router as dependency_router


app = FastAPI(
    title="KAIROS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Vite dev server (port 3000) and any other local origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Result-Truncated", "X-Total-Count"],
)


# ── Request-ID middleware ─────────────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Error handlers ────────────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return api_error(
        request=request,
        message="The requested resource was not found",
        status_code=404,
        code="NOT_FOUND",
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router,     prefix="/api/v1")
app.include_router(search_router,     prefix="/api/v1")
app.include_router(assets_router,     prefix="/api/v1")
app.include_router(lineage_router,    prefix="/api/v1")
app.include_router(dependency_router, prefix="/api/v1")
