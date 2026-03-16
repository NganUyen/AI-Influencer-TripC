from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from temporalio.client import Client

from config.settings import settings

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

    try:
        # Initialize Temporal client
        logger.info(f"Connecting to Temporal at {settings.TEMPORAL_ADDRESS}")
        temporal_client = await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )
        app.state.temporal_client = temporal_client
        logger.info("Temporal client connected successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down AI Influencer Factory Backend...")
    # Cleanup connections


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
            "openclaw": settings.OPENCLAW_API_URL,
            "postiz": settings.POSTIZ_API_URL,
            "growchief": settings.GROWCHIEF_API_URL,
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
from api import workflows, media, accounts, analytics, content

app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(media.router, prefix="/api/media", tags=["Media"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(content.router, prefix="/api/content", tags=["Content"])


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
