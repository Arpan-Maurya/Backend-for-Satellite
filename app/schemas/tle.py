"""
Pydantic models for TLE data input/output.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class TLEInput(BaseModel):
    """TLE data for a single satellite (input from API)."""

    line1: str = Field(
        ...,
        min_length=69,
        max_length=71,  # Allow CRLF
        description="TLE line 1 (69 characters)",
        examples=["1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021"],
    )
    line2: str = Field(
        ...,
        min_length=69,
        max_length=71,
        description="TLE line 2 (69 characters)",
        examples=["2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890"],
    )
    name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional satellite name",
        examples=["ISS (ZARYA)"],
    )

    @field_validator("line1")
    @classmethod
    def validate_line1(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("1 "):
            raise ValueError("TLE line 1 must start with '1 '")
        return v

    @field_validator("line2")
    @classmethod
    def validate_line2(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("2 "):
            raise ValueError("TLE line 2 must start with '2 '")
        return v


class TLEOutput(BaseModel):
    """TLE data in API responses."""

    norad_id: str
    name: Optional[str] = None
    line1: str
    line2: str
