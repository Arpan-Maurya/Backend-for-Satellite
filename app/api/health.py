"""
Health check API route.
"""

from fastapi import APIRouter
from app.schemas.common import HealthResponse
from app.config import get_settings
from app.ml.model_manager import model_manager

import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns service status, version, model readiness, and database connectivity.",
)
async def health_check() -> HealthResponse:
    settings = get_settings()

    # Check database connectivity
    db_connected = False
    try:
        from app.db.client import get_supabase_client
        client = get_supabase_client()
        client.table("satellites").select("id").limit(1).execute()
        db_connected = True
    except Exception as e:
        logger.warning("Health check: database unreachable — %s", e)

    return HealthResponse(
        status="healthy" if model_manager.is_loaded and db_connected else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        models_loaded=model_manager.is_loaded,
        mock_mode=model_manager.is_mock,
        database_connected=db_connected,
    )
