"""
TLE ingestion service — fetches TLE data from CelesTrak and persists to Supabase.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.core.exceptions import TLEFetchError, TLEValidationError
from app.core.tle_parser import parse_tle, parse_tle_batch, ParsedTLE
from app.db import satellite_repo

logger = logging.getLogger(__name__)

# Maximum allowed body size for TLE responses (10 MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024

# Allowed TLE fetch domains (SSRF protection)
ALLOWED_DOMAINS = {"celestrak.org", "celestrak.com", "www.celestrak.org", "www.celestrak.com"}


async def fetch_tle_from_celestrak(
    group: str = "stations",
    format_type: str = "tle",
) -> str:
    """
    Fetch TLE data from CelesTrak.

    Args:
        group: Satellite group (e.g., 'stations', 'starlink', 'active').
        format_type: Response format ('tle', '3le', 'json').

    Returns:
        Raw TLE text from CelesTrak.

    Raises:
        TLEFetchError: If request fails, times out, or returns bad data.
    """
    settings = get_settings()
    url = f"{settings.celestrak_base_url}?GROUP={group}&FORMAT={format_type}"

    # SSRF protection: validate URL domain
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_DOMAINS:
        raise TLEFetchError(f"Blocked request to unauthorized domain: {parsed.hostname}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Size check
            content = response.text
            if len(content) > MAX_RESPONSE_SIZE:
                raise TLEFetchError("TLE response exceeds maximum allowed size")

            if not content.strip():
                raise TLEFetchError("Empty response from CelesTrak")

            logger.info("Fetched %d bytes of TLE data from %s", len(content), url)
            return content

    except httpx.TimeoutException:
        raise TLEFetchError("CelesTrak request timed out after 30 seconds")
    except httpx.HTTPStatusError as e:
        raise TLEFetchError(f"CelesTrak returned HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        raise TLEFetchError(f"Network error fetching TLE data: {e}")
    except TLEFetchError:
        raise
    except Exception as e:
        raise TLEFetchError(f"Unexpected error fetching TLE data: {e}")


async def ingest_tle_group(group: str = "stations") -> int:
    """
    Fetch and ingest a TLE group into Supabase.

    Returns:
        Number of satellites successfully ingested.
    """
    raw_tle = await fetch_tle_from_celestrak(group=group)

    count = 0
    for parsed in parse_tle_batch(raw_tle):
        try:
            # Compute epoch datetime from TLE
            epoch_dt = _compute_epoch_datetime(parsed.epoch_year, parsed.epoch_day)

            satellite_repo.upsert_satellite(
                norad_id=parsed.norad_id,
                name=parsed.name,
                tle_line1=parsed.line1,
                tle_line2=parsed.line2,
                epoch_datetime=epoch_dt,
            )
            count += 1
        except Exception as e:
            logger.warning("Failed to ingest satellite %s: %s", parsed.norad_id, e)

    logger.info("Ingested %d satellites from group '%s'", count, group)
    return count


def _compute_epoch_datetime(epoch_year: int, epoch_day: float) -> datetime:
    """Convert TLE epoch (year + day-of-year) to datetime."""
    from datetime import timedelta
    base = datetime(epoch_year, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(days=epoch_day - 1)
