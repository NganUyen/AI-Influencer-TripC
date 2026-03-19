from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from temporalio.client import Client

from config.settings import settings
from services.content_persistence_service import ContentPersistenceService
from services.proxy_manager_service import ProxyManagerService

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Global Temporal client
temporal_client = None


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
    await ProxyManagerService.close_db_pool()


app = FastAPI(
    title="AI Influencer Factory API",
    description="Backend API for AI-driven marketing orchestration platform",
    version="0.1.0",
    lifespan=lifespan,
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
from api import workflows, media, accounts, analytics, content, quota, webhooks

app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(media.router, prefix="/api/media", tags=["Media"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(content.router, prefix="/api/content", tags=["Content"])
app.include_router(quota.router, prefix="/api/quota", tags=["Quota"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/api/personas")
async def list_personas():
    """List all AI personas"""
    # TODO: Implement persona listing
    return {"personas": []}


@app.post("/api/personas")
async def create_persona(name: str, description: str):
    """Create a new AI persona"""
    # TODO: Implement persona creation
    return {
        "message": f"Creating persona: {name}",
        "persona_id": "pending",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
