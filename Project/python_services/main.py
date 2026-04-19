from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import secrets
from temporalio.client import Client
from urllib.parse import urlparse

from api.security import require_internal_api_token
from config.settings import settings
from services.content_persistence_service import ContentPersistenceService
from services.database_service import DatabaseService
from services.proxy_manager_service import ProxyManagerService

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Global Temporal client
temporal_client = None


def _is_authenticated_internal_request(request: Request) -> bool:
    configured_token = (settings.INTERNAL_API_TOKEN or "").strip()
    if not configured_token:
        return False

    presented_token = (request.headers.get("x-internal-api-token") or "").strip()
    if not presented_token:
        authorization = (request.headers.get("authorization") or "").strip()
        if authorization.lower().startswith("bearer "):
            presented_token = authorization.split(" ", 1)[1].strip()
        else:
            presented_token = authorization

    return bool(presented_token) and secrets.compare_digest(
        presented_token,
        configured_token,
    )


def _allow_persona_studio_debug_detail(request: Request) -> bool:
    if not request.url.path.startswith("/api/customer/persona-studio"):
        return False
    return (request.headers.get("x-customer-debug-errors") or "").strip() == "1"


def _root_path_from_public_url(value: str | None) -> str:
    if not value:
        return ""
    path = (urlparse(value).path or "").rstrip("/")
    return "" if path in {"", "/"} else path


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global temporal_client

    # Startup
    logger.info("Starting AI Influencer Factory Backend...")
    temporal_client = None
    app.state.temporal_client = None

    try:
        # Initialize Temporal client
        logger.info(f"Connecting to Temporal at {settings.TEMPORAL_ADDRESS}")
        temporal_client = await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )
        app.state.temporal_client = temporal_client
        logger.info("Temporal client connected successfully")

    except Exception as e:
        logger.warning(
            "Temporal unavailable during startup, continuing in degraded mode: %s",
            str(e),
        )

    yield

    # Shutdown
    logger.info("Shutting down AI Influencer Factory Backend...")
    await ContentPersistenceService.close_pool()
    await DatabaseService.close_pool()
    await ProxyManagerService.close_db_pool()


backend_root_path = _root_path_from_public_url(settings.BACKEND_PUBLIC_URL)
app_kwargs = {}
if backend_root_path:
    app_kwargs["root_path"] = backend_root_path
    app_kwargs["servers"] = [{"url": backend_root_path}]

app = FastAPI(
    title="AI Influencer Factory API",
    description="Backend API for AI-driven marketing orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
    **app_kwargs,
)

allowed_origins = [
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def sanitize_http_exception(request: Request, exc: HTTPException):
    if (
        exc.status_code >= 500
        and not _is_authenticated_internal_request(request)
        and not _allow_persona_studio_debug_detail(request)
    ):
        logger.warning("Sanitizing backend %s response: %s", exc.status_code, exc.detail)
        detail = "Service unavailable" if exc.status_code == 503 else "Internal server error"
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=exc.headers,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.exception(
        "Unhandled backend error on %s %s",
        request.method,
        request.url.path,
    )
    if _allow_persona_studio_debug_detail(request):
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {exc}"},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Influencer Factory API",
        "version": "0.1.0",
        "status": "running",
        "services": {
            "temporal": "connected" if temporal_client else "disconnected",
            "openclaw": "configured" if settings.OPENCLAW_API_URL else "unavailable",
            "postiz": "configured" if settings.POSTIZ_API_URL else "unavailable",
            "growchief": "configured"
            if settings.GROWCHIEF_API_URL
            else "unavailable",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "temporal": "connected" if temporal_client else "disconnected",
    }


# Import API routes
from api import (
    workflows,
    media,
    accounts,
    analytics,
    content,
    quota,
    webhooks,
    telegram_webhook,
    personas,
    customer,
    telegram_auth,
    health,
)

app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(media.router, prefix="/api/media", tags=["Media"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(content.router, prefix="/api/content", tags=["Content"])
app.include_router(quota.router, prefix="/api/quota", tags=["Quota"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(
    telegram_webhook.router,
    prefix="/api/webhooks",
    tags=["Telegram"],
)
app.include_router(personas.router, prefix="/api/personas", tags=["Personas"])
app.include_router(customer.router, prefix="/api/customer", tags=["Customer"])
app.include_router(telegram_auth.router, prefix="/api/auth/telegram", tags=["Auth"])
app.include_router(health.router, prefix="/api/health", tags=["Health"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
