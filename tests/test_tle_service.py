"""
Tests for TLE ingestion service and CelesTrak fetching.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.services.tle_service import (
    fetch_tle_from_celestrak,
    ingest_tle_group,
    _compute_epoch_datetime,
    MAX_RESPONSE_SIZE,
)
from app.core.exceptions import TLEFetchError


@pytest.mark.asyncio
async def test_fetch_tle_success():
    sample_content = (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021\n"
        "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890\n"
    )

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = sample_content
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        data = await fetch_tle_from_celestrak(group="stations")
        assert "ISS (ZARYA)" in data
        assert "25544" in data


@pytest.mark.asyncio
async def test_fetch_tle_ssrf_blocked():
    with patch("app.services.tle_service.get_settings") as mock_settings:
        mock_s = MagicMock()
        mock_s.celestrak_base_url = "https://evil-attacker-site.com/elements"
        mock_settings.return_value = mock_s

        with pytest.raises(TLEFetchError, match="Blocked request to unauthorized domain"):
            await fetch_tle_from_celestrak()


@pytest.mark.asyncio
async def test_fetch_tle_timeout():
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(TLEFetchError, match="timed out"):
            await fetch_tle_from_celestrak()


@pytest.mark.asyncio
async def test_fetch_tle_empty_response():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "   \n  "
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(TLEFetchError, match="Empty response"):
            await fetch_tle_from_celestrak()


@pytest.mark.asyncio
async def test_ingest_tle_group():
    sample_content = (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021\n"
        "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890\n"
    )
    with patch("app.services.tle_service.fetch_tle_from_celestrak", return_value=sample_content):
        with patch("app.db.satellite_repo.upsert_satellite") as mock_upsert:
            count = await ingest_tle_group(group="stations")
            assert count == 1
            assert mock_upsert.called


def test_compute_epoch_datetime():
    dt = _compute_epoch_datetime(2024, 1.5)
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 1
