from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
from pathlib import Path

from backend.app.api.errors import api_error
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.search import router as search_router
from backend.app.api.routes.assets import router as assets_router
from backend.app.api.routes.lineage import router as lineage_router
from backend.app.api.routes.dependency import router as dependency_router
from backend.app.api.routes.rea import router as rea_router
from backend.app.api.routes.audit import router as audit_router
from backend.app.api.routes.owner import router as owner_router
from backend.app.api.routes.metadata import router as metadata_router
from backend.app.auth import auth_disabled, require_user, supabase_auth_url


app = FastAPI(
    title="KAIROS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    return api_error(request=request, message=str(exc.detail), status_code=401, code="UNAUTHENTICATED")


@app.exception_handler(503)
async def service_unavailable_handler(request: Request, exc):
    return api_error(request=request, message=str(exc.detail), status_code=503, code="AUTH_UNAVAILABLE")

# ── CORS ─────────────────────────────────────────────────────────────────────
# Vite origin locally and the configured frontend origin in hosted deployments.
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").rstrip("/")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=False,
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
app.include_router(rea_router,        prefix="/api/v1")
app.include_router(audit_router,      prefix="/api/v1")
app.include_router(owner_router,      prefix="/api/v1")
app.include_router(metadata_router,   prefix="/api/v1")


@app.get("/api/v1/auth/config", tags=["authentication"])
def auth_config():
    """Expose only the public Supabase client settings needed by the sign-in page."""
    return {
        "url": supabase_auth_url(),
        "publishable_key": os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY"),
        "auth_disabled": auth_disabled(),
    }


@app.get("/ingestion.html", include_in_schema=False)
def authenticated_ingestion_page(user: dict = Depends(require_user)):
    """Serve the standalone ingestion workspace only to signed-in users."""
    return FileResponse(FRONTEND_SOURCE_DIR / "ingestion.html", media_type="text/html")


# Keep API routes above this catch-all mount so the Hatchable-exported browser
# interface is served at / while API endpoints remain handled by FastAPI.
FRONTEND_SOURCE_DIR = Path(__file__).resolve().parents[2] / "frontend"
FRONTEND_DIR = FRONTEND_SOURCE_DIR / "dist"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
