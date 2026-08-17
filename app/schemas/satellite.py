"""
Pydantic models for satellite API responses.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SatelliteResponse(BaseModel):
    """Satellite record from the database."""

    id: str = Field(description="UUID")
    norad_id: str = Field(description="NORAD catalog ID")
    name: Optional[str] = Field(default=None, description="Satellite name")
    tle_line1: str = Field(description="TLE line 1")
    tle_line2: str = Field(description="TLE line 2")
    epoch_datetime: Optional[str] = Field(default=None, description="TLE epoch")
    created_at: Optional[str] = Field(default=None, description="Record creation time")
    updated_at: Optional[str] = Field(default=None, description="Last update time")


class SatelliteListResponse(BaseModel):
    """Paginated list of satellites."""

    satellites: list[SatelliteResponse] = Field(description="Satellite records")
    total: int = Field(description="Total count")
    limit: int = Field(description="Page size")
    offset: int = Field(description="Page offset")
