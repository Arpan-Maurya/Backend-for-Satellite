"""
FastAPI application entry point.

- Configures CORS, logging, exception handlers
- Loads ML models at startup
- Includes all API routers
- Provides graceful shutdown
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.exceptions import SatelliteBackendError
from app.core.limiter import limiter
from app.ml.model_manager import model_manager

# Configure logging before anything else
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # --- Startup ---
    logger.info("=" * 60)
    logger.info("Starting Satellite Collision Risk Assessment Backend")
    logger.info("Environment: %s | Version: %s", settings.environment, settings.app_version)
    logger.info("=" * 60)

    # Load ML models
    try:
        model_manager.load_models(
            model_dir=settings.model_dir,
            mock_mode=settings.mock_ml_mode,
        )
    except Exception as e:
        logger.error("Failed to load ML models: %s", e)
        if not settings.mock_ml_mode:
            logger.warning("Models not loaded — prediction endpoints will return 503")

    # Verify Supabase connectivity
    try:
        from app.db.client import get_supabase_client
        get_supabase_client()
        logger.info("✅ Supabase connected")
    except Exception as e:
        logger.error("⚠️  Supabase connection failed: %s", e)

    # Start TLE background scheduler if enabled
    if settings.enable_tle_scheduler:
        try:
            from app.services.scheduler import start_tle_scheduler
            start_tle_scheduler(interval_seconds=settings.tle_ingest_interval_seconds)
        except Exception as e:
            logger.warning("Failed to start TLE scheduler: %s", e)

    yield

    # --- Shutdown ---
    if settings.enable_tle_scheduler:
        try:
            from app.services.scheduler import stop_tle_scheduler
            await stop_tle_scheduler()
        except Exception as e:
            logger.warning("Error stopping TLE scheduler: %s", e)

    logger.info("Shutting down backend gracefully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Satellite Collision Risk Assessment API",
        description=(
            "AI-driven backend for assessing collision risk between mega-constellation satellites. "
            "Uses TLE data, orbital mechanics, and XGBoost ML models to predict minimum separation "
            "distance and collision probability."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- CORS Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        max_age=600,
    )

    # --- Rate Limiting ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # --- Exception Handlers ---
    @app.exception_handler(SatelliteBackendError)
    async def backend_error_handler(request: Request, exc: SatelliteBackendError):
        """Handle all custom backend exceptions with safe error responses."""
        logger.error("Backend error [%d]: %s", exc.status_code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Catch-all: never leak stack traces, paths, or secrets to the client."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
            },
        )

    # --- Include Routers ---
    from app.api.health import router as health_router
    from app.api.satellites import router as satellite_router
    from app.api.risk import router as risk_router
    from app.api.websocket import router as ws_router

    app.include_router(health_router)
    app.include_router(satellite_router)
    app.include_router(risk_router)
    app.include_router(ws_router)

    return app


# Application instance
app = create_app()
