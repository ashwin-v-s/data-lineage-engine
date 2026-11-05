import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.errors import api_error
from backend.app.api.routes.assets import router as assets_router
from backend.app.api.routes.audit import router as audit_router
from backend.app.api.routes.capabilities import router as capabilities_router
from backend.app.api.routes.dependency import router as dependency_router
from backend.app.api.routes.ingest import router as ingest_router
from backend.app.api.routes.governance import router as governance_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.ingest import router as ingest_router
from backend.app.api.routes.ingestion import router as ingestion_router
from backend.app.api.routes.integrations import router as integrations_router
from backend.app.api.routes.lineage import router as lineage_router
from backend.app.api.routes.membership import router as membership_router
from backend.app.api.routes.metadata import router as metadata_router
from backend.app.api.routes.owner import router as owner_router
from backend.app.api.routes.personalization import router as personalization_router
from backend.app.api.routes.rea import router as rea_router
from backend.app.api.routes.search import router as search_router
from backend.app.api.routes.sources import router as sources_router
from backend.app.api.routes.workspaces import router as workspaces_router
from backend.app.auth import auth_disabled, require_user, supabase_auth_url

# Largest request body the API will accept, in bytes.  Import payloads are
# untrusted input; capping the body keeps an oversized upload from consuming
# worker memory before any validation runs.  Override per environment.
MAX_REQUEST_BYTES = int(os.getenv("KAIROS_MAX_REQUEST_BYTES", str(1_000_000)))


app = FastAPI(
    title="KAIROS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    """Keep API failures machine-readable while retaining server diagnostics."""
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    logging.getLogger("kairos.api").exception(
        "Unhandled API error request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    return api_error(
        request=request,
        message="The server could not complete this request. Check the server log using the request ID.",
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
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
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Request body size guard ───────────────────────────────────────────────────
@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    """Reject oversized bodies before they are read or parsed.

    A declared ``Content-Length`` over the limit is refused immediately; a
    chunked body with no length is still bounded by the server's own read
    limits.  This guard is cheap and applies to every route, including the
    metadata import path.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            too_large = int(declared) > MAX_REQUEST_BYTES
        except ValueError:
            too_large = True
        if too_large:
            return api_error(
                request=request,
                message=f"Request body exceeds the {MAX_REQUEST_BYTES}-byte limit",
                status_code=413,
                code="PAYLOAD_TOO_LARGE",
            )
    return await call_next(request)


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
app.include_router(ingest_router,     prefix="/api/v1")
app.include_router(rea_router,        prefix="/api/v1")
app.include_router(audit_router,      prefix="/api/v1")
app.include_router(owner_router,      prefix="/api/v1")
app.include_router(metadata_router,   prefix="/api/v1")
app.include_router(personalization_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(membership_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(governance_router, prefix="/api/v1")
app.include_router(capabilities_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")


# ── Liveness probe ────────────────────────────────────────────────────────────
# Unauthenticated and dependency-free so a hosting platform (Vercel, a load
# balancer, an uptime monitor) can confirm the process is up.  It deliberately
# does NOT touch the database or Supabase: the authenticated, database-backed
# readiness check lives at GET /api/v1/health.  Declared before the catch-all
# StaticFiles mount below so it is never shadowed.
@app.get("/healthz", tags=["health"])
def liveness():
    return {"status": "ok", "service": "kairos-api"}


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
async def authenticated_ingestion_page(request: Request):
    """Serve the ingestion workspace to signed-in users.

    An unauthenticated browser navigation (no Authorization header) gets a
    302 redirect to the sign-in page instead of a raw JSON 401 body (J7).
    Only /api/* routes return JSON error envelopes.
    """
    from fastapi import HTTPException as _HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    # Build credentials from the raw header, if present.
    auth_header = request.headers.get("authorization", "")
    parts = auth_header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        creds: HTTPAuthorizationCredentials | None = HTTPAuthorizationCredentials(
            scheme=parts[0], credentials=parts[1]
        )
    else:
        creds = None

    try:
        async for _user in require_user(credentials=creds):  # type: ignore[arg-type]
            break
    except _HTTPException:
        return RedirectResponse(url="/?signin_required=1", status_code=302)
    except Exception:
        return RedirectResponse(url="/?signin_required=1", status_code=302)

    return FileResponse(FRONTEND_SOURCE_DIR / "ingestion.html", media_type="text/html")


# Keep API routes above this catch-all mount so the Hatchable-exported browser
# interface is served at / while API endpoints remain handled by FastAPI.
FRONTEND_SOURCE_DIR = Path(__file__).resolve().parents[2] / "frontend"
FRONTEND_DIR = FRONTEND_SOURCE_DIR / "dist"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")




