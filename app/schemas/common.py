"""
Common/shared Pydantic response models.
"""

from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = Field(description="Service health status")
    version: str = Field(description="Application version")
    environment: str = Field(description="Deployment environment")
    models_loaded: bool = Field(description="Whether ML models are loaded")
    mock_mode: bool = Field(description="Whether running in mock ML mode")
    database_connected: bool = Field(description="Whether Supabase is reachable")


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str = Field(description="Error type/category")
    message: str = Field(description="Human-readable error message")
    detail: Optional[str] = Field(default=None, description="Additional detail (non-sensitive)")
