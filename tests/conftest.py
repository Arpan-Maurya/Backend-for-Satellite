"""
Shared test fixtures and configuration.
"""

import os
import pytest

# Set test environment variables BEFORE importing app modules
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "test-service-key"
os.environ["MOCK_ML_MODE"] = "true"
os.environ["ENVIRONMENT"] = "testing"
os.environ["MODEL_DIR"] = "./models"
os.environ["FRONTEND_URL"] = "http://localhost:8501"

from app.config import get_settings, Settings


# ---- Sample TLE Data (real ISS and STARLINK TLEs) ----

# ISS (ZARYA) — real TLE format (with valid checksums)
SAMPLE_TLE_1_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021"
SAMPLE_TLE_1_LINE2 = "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890"
SAMPLE_TLE_1_NAME = "ISS (ZARYA)"

# A second satellite TLE for pair testing
SAMPLE_TLE_2_LINE1 = "1 48274U 21035A   24001.50000000  .00002000  00000-0  15000-3 0  9999"
SAMPLE_TLE_2_LINE2 = "2 48274  53.0500 120.0000 0001000  90.0000 270.0000 15.06400000100009"
SAMPLE_TLE_2_NAME = "STARLINK-TEST"


@pytest.fixture
def sample_tle_1():
    return {
        "line1": SAMPLE_TLE_1_LINE1,
        "line2": SAMPLE_TLE_1_LINE2,
        "name": SAMPLE_TLE_1_NAME,
    }


@pytest.fixture
def sample_tle_2():
    return {
        "line1": SAMPLE_TLE_2_LINE1,
        "line2": SAMPLE_TLE_2_LINE2,
        "name": SAMPLE_TLE_2_NAME,
    }


@pytest.fixture
def client():
    """Create test client with mocked Supabase client."""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient

    with patch("app.db.client.create_client") as mock_create:
        mock_sb = MagicMock()
        mock_create.return_value = mock_sb

        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.range.return_value = mock_table

        mock_result = MagicMock()
        mock_result.data = [{
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "norad_id": "25544",
            "name": "ISS (ZARYA)",
            "tle_line1": SAMPLE_TLE_1_LINE1,
            "tle_line2": SAMPLE_TLE_1_LINE2,
            "epoch_datetime": "2024-01-01T12:00:00Z",
            "created_at": "2026-08-16T12:00:00Z",
            "updated_at": "2026-08-16T12:00:00Z",
        }]
        mock_result.count = 1
        mock_table.execute.return_value = mock_result

        from app.main import app
        from app.ml.model_manager import model_manager
        model_manager.load_models("./models", mock_mode=True)

        with TestClient(app) as test_client:
            yield test_client

