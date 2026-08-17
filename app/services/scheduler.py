"""
Daily TLE Ingestion Scheduler.

Runs in the background during application lifespan to periodically refresh
satellite TLE data from CelesTrak.
"""

import asyncio
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Background task handle
_scheduler_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


async def _run_periodic_ingestion(stop_evt: asyncio.Event, interval_seconds: int = 86400, group: str = "stations") -> None:
    """Internal loop that runs TLE ingestion at periodic intervals."""
    from app.services.tle_service import ingest_tle_group

    logger.info("TLE background scheduler loop started (interval: %ds, group: %s)", interval_seconds, group)

    while not stop_evt.is_set():
        try:
            logger.info("Running scheduled TLE ingestion for group '%s'...", group)
            count = await ingest_tle_group(group=group)
            logger.info("Scheduled TLE ingestion completed: %d satellites updated", count)
        except Exception as e:
            logger.warning("Scheduled TLE ingestion failed (will retry next interval): %s", e)

        try:
            # Wait for next interval or until stopped
            await asyncio.wait_for(stop_evt.wait(), timeout=float(interval_seconds))
        except asyncio.TimeoutError:
            pass  # Interval elapsed, loop again


def start_tle_scheduler(interval_seconds: Optional[int] = None, group: str = "stations") -> Optional[asyncio.Task]:
    """
    Start the background TLE ingestion scheduler.

    Args:
        interval_seconds: Seconds between runs (default from settings: 86400s / 24h).
        group: CelesTrak satellite group to ingest.

    Returns:
        The running asyncio.Task, or None if already running.
    """
    global _scheduler_task, _stop_event

    if _scheduler_task is not None and not _scheduler_task.done():
        logger.warning("TLE scheduler is already running")
        return _scheduler_task

    settings = get_settings()
    if interval_seconds is None:
        interval_seconds = getattr(settings, "tle_ingest_interval_seconds", 86400)

    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _run_periodic_ingestion(stop_evt=_stop_event, interval_seconds=interval_seconds, group=group)
    )
    logger.info("TLE background scheduler started")
    return _scheduler_task


async def stop_tle_scheduler() -> None:
    """Gracefully stop the background TLE scheduler."""
    global _scheduler_task, _stop_event

    if _scheduler_task is None or _scheduler_task.done():
        return

    logger.info("Stopping TLE background scheduler...")
    _stop_event.set()
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    finally:
        _scheduler_task = None
        logger.info("TLE background scheduler stopped")
