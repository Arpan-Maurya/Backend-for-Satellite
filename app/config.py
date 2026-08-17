"""
Application configuration loaded from environment variables.
Uses pydantic-settings for type-safe config with validation.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """All backend configuration. Loaded from .env / environment variables."""

    # --- Supabase ---
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_key: str = Field(..., description="Supabase service-role key (server-side only)")

    # --- CelesTrak & Scheduler ---
    celestrak_base_url: str = Field(
        default="https://celestrak.org/NORAD/elements/gp.php",
        description="CelesTrak TLE data endpoint",
    )
    enable_tle_scheduler: bool = Field(
        default=False,
        description="Whether to run automatic background TLE ingestion scheduler",
    )
    tle_ingest_interval_seconds: int = Field(
        default=86400,
        description="Interval in seconds for TLE ingestion (default: 86400 = 24h)",
    )

    # --- ML Models ---
    model_dir: str = Field(default="./models", description="Directory containing .pkl model files")
    mock_ml_mode: bool = Field(default=False, description="If true, use mock predictions instead of real models")

    # --- Application ---
    environment: str = Field(default="development", description="development | staging | production")
    log_level: str = Field(default="INFO", description="Python logging level")
    port: int = Field(default=8000, description="Server port")
    app_version: str = Field(default="1.0.0", description="Application version")

    # --- CORS ---
    frontend_url: str = Field(
        default="http://localhost:8501",
        description="Comma-separated allowed origins for CORS",
    )

    # --- Risk Engine Thresholds ---
    risk_msd_threshold: float = Field(
        default=1000.0,
        description="MSD threshold in meters for normalization (closer = higher risk)",
    )
    risk_critical: float = Field(default=0.8, description="Score >= this = CRITICAL")
    risk_high: float = Field(default=0.6, description="Score >= this = HIGH")
    risk_medium: float = Field(default=0.3, description="Score >= this = MEDIUM")
    # Below risk_medium = LOW

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated frontend URLs into a list."""
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()
