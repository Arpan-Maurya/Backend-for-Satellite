"""
Tests for Supabase repositories and database exception handling.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.db import satellite_repo, assessment_repo, alert_repo
from app.core.exceptions import (
    SatelliteNotFoundError,
    AssessmentNotFoundError,
    DatabaseError,
)


def _build_mock_client(data):
    """Helper to build a mock Supabase client where all chained queries resolve to given data."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table

    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.range.return_value = mock_table

    mock_exec = MagicMock()
    mock_exec.data = data
    mock_exec.count = len(data)
    mock_table.execute.return_value = mock_exec

    return mock_sb


def test_satellite_repo_upsert():
    mock_sb = _build_mock_client([{"id": "sat-1", "norad_id": "25544"}])
    with patch("app.db.satellite_repo.get_supabase_client", return_value=mock_sb):
        res = satellite_repo.upsert_satellite(
            norad_id="25544",
            name="ISS",
            tle_line1="1 25544...",
            tle_line2="2 25544...",
        )
        assert res.get("norad_id") == "25544"


def test_satellite_repo_not_found():
    mock_sb = _build_mock_client([])
    with patch("app.db.satellite_repo.get_supabase_client", return_value=mock_sb):
        with pytest.raises(SatelliteNotFoundError):
            satellite_repo.get_satellite_by_norad_id("99999")


def test_assessment_repo_insert_and_get():
    mock_sb = _build_mock_client([{"id": "uuid-1", "risk_score": 0.85}])
    with patch("app.db.assessment_repo.get_supabase_client", return_value=mock_sb):
        saved = assessment_repo.create_assessment(
            sat1_norad_id="25544",
            sat2_norad_id="48274",
            msd_predicted=500.0,
            collision_prob=0.01,
            risk_score=0.85,
            risk_tier="HIGH",
            confidence=0.9,
            model_version="mock-v1.0.0",
        )
        assert saved.get("id") == "uuid-1"

        top = assessment_repo.get_top_conjunctions(limit=5)
        assert len(top) == 1


def test_assessment_repo_not_found():
    mock_sb = _build_mock_client([])
    with patch("app.db.assessment_repo.get_supabase_client", return_value=mock_sb):
        with pytest.raises(AssessmentNotFoundError):
            assessment_repo.get_assessment_by_id("non-existent-uuid")


def test_alert_repo_create_and_get():
    mock_sb = _build_mock_client([{"id": "alert-1", "risk_tier": "CRITICAL"}])
    with patch("app.db.alert_repo.get_supabase_client", return_value=mock_sb):
        alert = alert_repo.create_alert(
            sat1_norad_id="25544",
            sat2_norad_id="48274",
            risk_tier="CRITICAL",
            message="Critical risk detected",
        )
        assert alert.get("id") == "alert-1"

        recent = alert_repo.list_alerts(limit=10)
        assert len(recent) == 1
