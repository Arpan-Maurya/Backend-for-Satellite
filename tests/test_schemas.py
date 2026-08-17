"""
Tests for Pydantic schema validation.
"""

import pytest
from pydantic import ValidationError
from app.schemas.tle import TLEInput
from app.schemas.risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.schemas.common import HealthResponse, ErrorResponse
from tests.conftest import SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2


class TestTLEInputSchema:
    def test_valid_tle(self):
        tle = TLEInput(line1=SAMPLE_TLE_1_LINE1, line2=SAMPLE_TLE_1_LINE2)
        assert tle.line1 == SAMPLE_TLE_1_LINE1
        assert tle.line2 == SAMPLE_TLE_1_LINE2

    def test_line1_must_start_with_1(self):
        with pytest.raises(ValidationError):
            TLEInput(line1="2 " + "x" * 67, line2=SAMPLE_TLE_1_LINE2)

    def test_line2_must_start_with_2(self):
        with pytest.raises(ValidationError):
            TLEInput(line1=SAMPLE_TLE_1_LINE1, line2="1 " + "x" * 67)

    def test_too_short(self):
        with pytest.raises(ValidationError):
            TLEInput(line1="1 short", line2=SAMPLE_TLE_1_LINE2)

    def test_name_optional(self):
        tle = TLEInput(line1=SAMPLE_TLE_1_LINE1, line2=SAMPLE_TLE_1_LINE2)
        assert tle.name is None

    def test_name_provided(self):
        tle = TLEInput(
            line1=SAMPLE_TLE_1_LINE1,
            line2=SAMPLE_TLE_1_LINE2,
            name="ISS"
        )
        assert tle.name == "ISS"


class TestRiskAssessmentResponse:
    def test_valid_response(self):
        resp = RiskAssessmentResponse(
            sat1_norad_id="25544",
            sat2_norad_id="48274",
            msd_predicted_meters=342.7,
            collision_probability=0.023,
            normalized_msd_risk=0.657,
            risk_score=0.277,
            risk_tier="LOW",
            confidence=0.87,
            model_version="v1.0.0",
            timestamp="2026-08-16T12:00:00Z",
        )
        assert resp.risk_tier == "LOW"

    def test_all_tiers_valid(self):
        for tier in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            resp = RiskAssessmentResponse(
                sat1_norad_id="A",
                sat2_norad_id="B",
                msd_predicted_meters=100,
                collision_probability=0.5,
                normalized_msd_risk=0.5,
                risk_score=0.5,
                risk_tier=tier,
                confidence=0.5,
                model_version="v1",
                timestamp="2026-01-01T00:00:00Z",
            )
            assert resp.risk_tier == tier


class TestHealthResponse:
    def test_all_fields(self):
        h = HealthResponse(
            status="healthy",
            version="1.0.0",
            environment="testing",
            models_loaded=True,
            mock_mode=True,
            database_connected=True,
        )
        assert h.status == "healthy"


class TestErrorResponse:
    def test_error_response(self):
        e = ErrorResponse(error="NotFound", message="Resource not found")
        assert e.error == "NotFound"
        assert e.detail is None
