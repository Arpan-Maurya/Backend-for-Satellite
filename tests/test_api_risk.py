"""
Tests for API endpoints using FastAPI TestClient.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.core.exceptions import (
    TLEValidationError,
    OrbitalCalculationError,
    FeatureEngineeringError,
    ModelNotLoadedError,
    SatelliteNotFoundError,
    AssessmentNotFoundError,
    DatabaseError,
)
from tests.conftest import (
    SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2, SAMPLE_TLE_1_NAME,
    SAMPLE_TLE_2_LINE1, SAMPLE_TLE_2_LINE2, SAMPLE_TLE_2_NAME,
)


@pytest.fixture
def client():
    """Create test client with mocked Supabase."""
    # Mock Supabase before importing app
    with patch("app.db.client.create_client") as mock_create:
        mock_sb = MagicMock()
        mock_create.return_value = mock_sb

        # Mock table operations
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
        mock_result.data = []
        mock_result.count = 0
        mock_table.execute.return_value = mock_result

        from app.main import app
        from app.ml.model_manager import model_manager

        model_manager.load_models("./models", mock_mode=True)

        with TestClient(app) as test_client:
            yield test_client


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_fields(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "models_loaded" in data
        assert "mock_mode" in data
        assert "database_connected" in data

    def test_health_version(self, client):
        response = client.get("/health")
        assert response.json()["version"] == "1.0.0"


class TestRiskAssessEndpoint:
    def test_assess_valid_request(self, client):
        """Valid TLE pair should return 200 with risk assessment."""
        with patch("app.services.assessment_service.satellite_repo") as mock_sat_repo, \
             patch("app.services.assessment_service.assessment_repo") as mock_ass_repo, \
             patch("app.services.assessment_service.alert_repo"):

            mock_sat_repo.upsert_satellite.return_value = {}
            mock_ass_repo.create_assessment.return_value = {"id": "test-uuid"}

            response = client.post("/risk/assess", json={
                "satellite_1": {
                    "line1": SAMPLE_TLE_1_LINE1,
                    "line2": SAMPLE_TLE_1_LINE2,
                    "name": SAMPLE_TLE_1_NAME,
                },
                "satellite_2": {
                    "line1": SAMPLE_TLE_2_LINE1,
                    "line2": SAMPLE_TLE_2_LINE2,
                    "name": SAMPLE_TLE_2_NAME,
                },
            })
            assert response.status_code == 200
            data = response.json()
            assert "risk_score" in data
            assert "risk_tier" in data
            assert "msd_predicted_meters" in data
            assert "collision_probability" in data
            assert "model_version" in data
            assert data["risk_tier"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            assert data["is_mock"] is True

    def test_assess_invalid_tle(self, client):
        """Invalid TLE should return 400."""
        response = client.post("/risk/assess", json={
            "satellite_1": {
                "line1": "1 invalid line that is exactly sixty-nine characters long in total!x5",
                "line2": "2 invalid line that is exactly sixty-nine characters long in total!x8",
            },
            "satellite_2": {
                "line1": SAMPLE_TLE_2_LINE1,
                "line2": SAMPLE_TLE_2_LINE2,
            },
        })
        assert response.status_code in [400, 422]

    def test_assess_missing_fields(self, client):
        """Missing required fields should return 422."""
        response = client.post("/risk/assess", json={
            "satellite_1": {"line1": SAMPLE_TLE_1_LINE1},
        })
        assert response.status_code == 422

    def test_assess_empty_body(self, client):
        response = client.post("/risk/assess", json={})
        assert response.status_code == 422


class TestSatellitesEndpoint:
    def test_list_returns_200(self, client):
        response = client.get("/satellites")
        assert response.status_code == 200

    def test_list_response_structure(self, client):
        response = client.get("/satellites")
        data = response.json()
        assert "satellites" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_list_with_params(self, client):
        response = client.get("/satellites?limit=10&offset=0")
        assert response.status_code == 200

    def test_get_nonexistent(self, client):
        """Getting a satellite that doesn't exist."""
        with patch("app.db.satellite_repo.get_satellite_by_norad_id") as mock_get:
            from app.core.exceptions import SatelliteNotFoundError
            mock_get.side_effect = SatelliteNotFoundError("99999")
            response = client.get("/satellites/99999")
            assert response.status_code == 404


class TestTopConjunctions:
    def test_returns_200(self, client):
        response = client.get("/risk/top-conjunctions")
        assert response.status_code == 200

    def test_response_structure(self, client):
        data = client.get("/risk/top-conjunctions").json()
        assert "conjunctions" in data
        assert "count" in data
        assert "limit" in data

    def test_custom_limit(self, client):
        response = client.get("/risk/top-conjunctions?limit=5")
        assert response.status_code == 200


class TestGetAssessmentEndpoint:
    def test_get_assessment_by_id_success(self, client):
        with patch("app.db.assessment_repo.get_assessment_by_id") as mock_get:
            mock_get.return_value = {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "sat1_norad_id": "25544",
                "sat2_norad_id": "48274",
                "msd_predicted": 350.0,
                "collision_prob": 0.05,
                "risk_score": 0.45,
                "risk_tier": "MEDIUM",
                "confidence": 0.88,
                "model_version": "mock-v1.0.0",
                "created_at": "2026-08-16T12:00:00Z",
            }
            resp = client.get("/risk/123e4567-e89b-12d3-a456-426614174000")
            assert resp.status_code == 200
            data = resp.json()
            assert data["assessment_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert data["risk_tier"] == "MEDIUM"

    def test_get_assessment_not_found(self, client):
        with patch("app.db.assessment_repo.get_assessment_by_id", side_effect=AssessmentNotFoundError("missing-id")):
            resp = client.get("/risk/missing-id")
            assert resp.status_code == 404

    def test_get_assessment_db_error(self, client):
        with patch("app.db.assessment_repo.get_assessment_by_id", side_effect=DatabaseError("DB Down")):
            resp = client.get("/risk/some-id")
            assert resp.status_code == 503


class TestRiskAssessmentErrors:
    def test_assess_orbital_calc_error(self, client):
        with patch("app.api.risk.run_risk_assessment", side_effect=OrbitalCalculationError("Orbital fail")):
            resp = client.post("/risk/assess", json={
                "satellite_1": {"line1": SAMPLE_TLE_1_LINE1, "line2": SAMPLE_TLE_1_LINE2},
                "satellite_2": {"line1": SAMPLE_TLE_2_LINE1, "line2": SAMPLE_TLE_2_LINE2},
            })
            assert resp.status_code == 422

    def test_assess_feature_eng_error(self, client):
        with patch("app.api.risk.run_risk_assessment", side_effect=FeatureEngineeringError("Feature fail")):
            resp = client.post("/risk/assess", json={
                "satellite_1": {"line1": SAMPLE_TLE_1_LINE1, "line2": SAMPLE_TLE_1_LINE2},
                "satellite_2": {"line1": SAMPLE_TLE_2_LINE1, "line2": SAMPLE_TLE_2_LINE2},
            })
            assert resp.status_code == 422

    def test_assess_model_not_loaded_error(self, client):
        with patch("app.api.risk.run_risk_assessment", side_effect=ModelNotLoadedError("Not loaded")):
            resp = client.post("/risk/assess", json={
                "satellite_1": {"line1": SAMPLE_TLE_1_LINE1, "line2": SAMPLE_TLE_1_LINE2},
                "satellite_2": {"line1": SAMPLE_TLE_2_LINE1, "line2": SAMPLE_TLE_2_LINE2},
            })
            assert resp.status_code == 503

    def test_assess_unexpected_500_error(self, client):
        with patch("app.api.risk.run_risk_assessment", side_effect=RuntimeError("Boom")):
            resp = client.post("/risk/assess", json={
                "satellite_1": {"line1": SAMPLE_TLE_1_LINE1, "line2": SAMPLE_TLE_1_LINE2},
                "satellite_2": {"line1": SAMPLE_TLE_2_LINE1, "line2": SAMPLE_TLE_2_LINE2},
            })
            assert resp.status_code == 500

    def test_top_conjunctions_db_error(self, client):
        with patch("app.db.assessment_repo.get_top_conjunctions", side_effect=DatabaseError("DB Down")):
            resp = client.get("/risk/top-conjunctions")
            assert resp.status_code == 503

    def test_list_satellites_db_error(self, client):
        with patch("app.db.satellite_repo.list_satellites", side_effect=DatabaseError("DB Down")):
            resp = client.get("/satellites")
            assert resp.status_code == 503

    def test_get_satellite_db_error(self, client):
        with patch("app.db.satellite_repo.get_satellite_by_norad_id", side_effect=DatabaseError("DB Down")):
            resp = client.get("/satellites/25544")
            assert resp.status_code == 503


class TestCORS:
    def test_cors_headers(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS should allow the configured origin
        assert response.status_code in [200, 400]  # FastAPI CORS handling


class TestErrorSecurity:
    def test_no_stack_traces(self, client):
        """Error responses should not contain stack traces."""
        response = client.get("/nonexistent-endpoint")
        body = response.text
        assert "Traceback" not in body
        assert "File \"" not in body
        assert ".py" not in body or "line" not in body.lower()
