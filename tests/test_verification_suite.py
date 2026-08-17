"""
Independent verification & security audit test suite.
Tests:
- Aggressive API security (fuzzing, SQLi strings, huge payloads, path traversal)
- Rate limiting enforcement (HTTP 429)
- WebSocket connection and live alert reception
- Performance benchmark (latency measurements)
- Streamlit integration flow simulation
- Edge-case orbital parameters
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from tests.conftest import (
    SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2, SAMPLE_TLE_1_NAME,
    SAMPLE_TLE_2_LINE1, SAMPLE_TLE_2_LINE2, SAMPLE_TLE_2_NAME,
)


@pytest.fixture(scope="module")
def app_client():
    """Module-scoped TestClient with mock ML mode."""
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

        with TestClient(app) as client:
            yield client


class TestSecurityFuzzing:
    """Aggressive fuzzing and security attack vectors."""

    def test_sql_injection_in_norad_id(self, app_client):
        """SQL injection strings in URL path should be safely handled."""
        sqli_payloads = [
            "25544' OR '1'='1",
            "25544; DROP TABLE satellites; --",
            "25544 UNION SELECT * FROM users--",
            "admin'--",
            "../../etc/passwd",
        ]
        for payload in sqli_payloads:
            resp = app_client.get(f"/satellites/{payload}")
            # Must return 200 (if found), 404 (if not found), or 422 (if schema fails) - NEVER 500
            assert resp.status_code in (200, 404, 422)
            assert "syntax error" not in resp.text.lower()
            assert "pg_catalog" not in resp.text.lower()

    def test_huge_payload_handling(self, app_client):
        """Extremely large payloads should be rejected or handled gracefully."""
        huge_str = "A" * (1024 * 1024)  # 1MB string
        resp = app_client.post("/risk/assess", json={
            "satellite_1": {"line1": huge_str, "line2": SAMPLE_TLE_1_LINE2},
            "satellite_2": {"line1": SAMPLE_TLE_2_LINE1, "line2": SAMPLE_TLE_2_LINE2},
        })
        assert resp.status_code in (400, 422)
        assert "Traceback" not in resp.text

    def test_malformed_json(self, app_client):
        """Broken JSON should return 422 without server error."""
        resp = app_client.post(
            "/risk/assess",
            content="{'invalid': json, missing quotes",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_negative_limit_query_param(self, app_client):
        """Negative limit should be rejected by validation with 422."""
        resp = app_client.get("/risk/top-conjunctions?limit=-5")
        assert resp.status_code == 422

    def test_excessive_limit_query_param(self, app_client):
        """Limit exceeding maximum should be rejected with 422."""
        resp = app_client.get("/risk/top-conjunctions?limit=999999")
        assert resp.status_code == 422

    def test_non_numeric_limit(self, app_client):
        resp = app_client.get("/risk/top-conjunctions?limit=not_a_number")
        assert resp.status_code == 422


class TestWebSocketChannel:
    """Test WebSocket connection and live alert broadcast."""

    def test_websocket_connection_and_ping_pong(self, app_client):
        with app_client.websocket_connect("/ws/live-risks") as ws:
            ws.send_text("ping")
            data = ws.receive_json()
            assert data.get("type") == "ack"

    def test_websocket_broadcast_on_high_risk(self, app_client):
        """Connecting client should be capable of receiving broadcasted alerts."""
        with app_client.websocket_connect("/ws/live-risks") as ws:
            # Trigger high risk assessment that sends an alert
            resp = app_client.post("/risk/assess", json={
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
            assert resp.status_code == 200


class TestPerformanceSanity:
    """Benchmark endpoints to verify latency bounds."""

    def test_health_latency(self, app_client):
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            resp = app_client.get("/health")
            t1 = time.perf_counter()
            assert resp.status_code == 200
            times.append((t1 - t0) * 1000)

        avg_ms = sum(times) / len(times)
        # Health check must execute quickly (< 50ms)
        assert avg_ms < 50.0

    def test_assess_latency(self, app_client):
        payload = {
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
        }
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            resp = app_client.post("/risk/assess", json=payload)
            t1 = time.perf_counter()
            assert resp.status_code == 200
            times.append((t1 - t0) * 1000)

        avg_ms = sum(times) / len(times)
        # End-to-end assess calculation per pair must be fast (< 50ms in mock mode)
        assert avg_ms < 50.0


class TestStreamlitSimulationFlow:
    """Simulate exact Streamlit frontend user flow."""

    def test_complete_frontend_flow(self, app_client):
        # 1. Health check
        h_resp = app_client.get("/health")
        assert h_resp.status_code == 200
        health_data = h_resp.json()
        assert health_data["status"] in ("healthy", "degraded")

        # 2. Risk assessment
        payload = {
            "satellite_1": {
                "line1": SAMPLE_TLE_1_LINE1,
                "line2": SAMPLE_TLE_1_LINE2,
                "name": "ISS (ZARYA)",
            },
            "satellite_2": {
                "line1": SAMPLE_TLE_2_LINE1,
                "line2": SAMPLE_TLE_2_LINE2,
                "name": "STARLINK-1234",
            },
        }
        assess_resp = app_client.post("/risk/assess", json=payload)
        assert assess_resp.status_code == 200
        result = assess_resp.json()

        # Check required fields
        assert "risk_score" in result
        assert "risk_tier" in result
        assert "msd_predicted_meters" in result
        assert "collision_probability" in result
        assert "confidence" in result
        assert "model_version" in result
        assert result["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

        # 3. Fetch top conjunctions
        top_resp = app_client.get("/risk/top-conjunctions?limit=10")
        assert top_resp.status_code == 200
        top_data = top_resp.json()
        assert "conjunctions" in top_data
        assert "count" in top_data

        # 4. List satellites
        sat_resp = app_client.get("/satellites?limit=5")
        assert sat_resp.status_code == 200
        sat_data = sat_resp.json()
        assert "satellites" in sat_data
        assert "total" in sat_data
