"""
Pydantic models for risk assessment API request/response.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.schemas.tle import TLEInput


class RiskAssessmentRequest(BaseModel):
    """Request body for POST /risk/assess."""

    satellite_1: TLEInput = Field(description="TLE data for first satellite")
    satellite_2: TLEInput = Field(description="TLE data for second satellite")


class RiskAssessmentResponse(BaseModel):
    """Full risk assessment result."""

    assessment_id: Optional[str] = Field(default=None, description="UUID of stored assessment")
    sat1_norad_id: str = Field(description="NORAD ID of satellite 1")
    sat2_norad_id: str = Field(description="NORAD ID of satellite 2")
    sat1_name: Optional[str] = Field(default=None, description="Name of satellite 1")
    sat2_name: Optional[str] = Field(default=None, description="Name of satellite 2")
    msd_predicted_meters: float = Field(description="Predicted minimum separation distance in meters")
    collision_probability: float = Field(description="Predicted collision probability [0,1]")
    normalized_msd_risk: float = Field(description="Normalized MSD risk component [0,1]")
    risk_score: float = Field(description="Combined risk score [0,1] (60% prob + 40% MSD)")
    risk_tier: str = Field(description="Risk classification: LOW, MEDIUM, HIGH, or CRITICAL")
    confidence: float = Field(description="Prediction confidence [0,1]")
    model_version: str = Field(description="ML model version used for prediction")
    is_mock: bool = Field(default=False, description="True if using mock predictions (dev only)")
    timestamp: str = Field(description="Assessment timestamp (ISO 8601)")

    model_config = {"json_schema_extra": {
        "examples": [{
            "assessment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "sat1_norad_id": "25544",
            "sat2_norad_id": "48274",
            "sat1_name": "ISS (ZARYA)",
            "sat2_name": "STARLINK-3456",
            "msd_predicted_meters": 342.7,
            "collision_probability": 0.0234,
            "normalized_msd_risk": 0.6573,
            "risk_score": 0.2770,
            "risk_tier": "LOW",
            "confidence": 0.87,
            "model_version": "v1.0.0",
            "is_mock": False,
            "timestamp": "2026-08-16T12:00:00Z",
        }]
    }}


class TopConjunctionsResponse(BaseModel):
    """Response for GET /risk/top-conjunctions."""

    conjunctions: list[RiskAssessmentResponse] = Field(
        description="List of highest-risk assessments"
    )
    count: int = Field(description="Number of results returned")
    limit: int = Field(description="Requested limit")
