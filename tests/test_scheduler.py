"""
Tests for TLE background scheduler.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from app.services.scheduler import (
    start_tle_scheduler,
    stop_tle_scheduler,
    _run_periodic_ingestion,
)


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Verify scheduler starts, handles tasks, and shuts down cleanly."""
    with patch("app.services.tle_service.ingest_tle_group", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = 5

        # Start scheduler with short interval
        task = start_tle_scheduler(interval_seconds=1, group="stations")
        assert task is not None
        assert not task.done()

        # Starting again should return same task without duplicate
        task2 = start_tle_scheduler(interval_seconds=1)
        assert task2 == task

        # Allow it to run one iteration
        await asyncio.sleep(0.05)
        assert mock_ingest.called

        # Stop scheduler gracefully
        await stop_tle_scheduler()
        assert task.done()


@pytest.mark.asyncio
async def test_scheduler_error_resilience():
    """Verify exceptions during ingestion do not crash the scheduler loop."""
    with patch("app.services.tle_service.ingest_tle_group", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.side_effect = RuntimeError("Network error")

        task = start_tle_scheduler(interval_seconds=1)
        await asyncio.sleep(0.05)

        # Ingestion was attempted
        assert mock_ingest.called
        # Task remains running (not crashed)
        assert not task.done()

        await stop_tle_scheduler()
