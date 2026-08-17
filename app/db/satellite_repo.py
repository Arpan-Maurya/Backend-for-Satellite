"""
Satellite repository — Supabase CRUD for the satellites table.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.core.exceptions import SatelliteNotFoundError, DatabaseError
from app.db.client import get_supabase_client

logger = logging.getLogger(__name__)

TABLE = "satellites"


def upsert_satellite(
    norad_id: str,
    name: Optional[str],
    tle_line1: str,
    tle_line2: str,
    epoch_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Insert or update a satellite record (keyed on norad_id).

    Returns:
        The upserted row as a dict.
    """
    try:
        client = get_supabase_client()
        data = {
            "norad_id": norad_id,
            "name": name or "",
            "tle_line1": tle_line1,
            "tle_line2": tle_line2,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if epoch_datetime:
            data["epoch_datetime"] = epoch_datetime.isoformat()

        result = (
            client.table(TABLE)
            .upsert(data, on_conflict="norad_id")
            .execute()
        )
        logger.debug("Upserted satellite %s", norad_id)
        return result.data[0] if result.data else data

    except Exception as e:
        logger.error("Failed to upsert satellite %s: %s", norad_id, e)
        raise DatabaseError(f"Failed to upsert satellite {norad_id}")


def get_satellite_by_norad_id(norad_id: str) -> Dict[str, Any]:
    """
    Fetch a satellite by NORAD ID.

    Returns:
        Satellite row dict.

    Raises:
        SatelliteNotFoundError: If not found.
    """
    try:
        client = get_supabase_client()
        result = (
            client.table(TABLE)
            .select("*")
            .eq("norad_id", norad_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise SatelliteNotFoundError(norad_id)
        return result.data[0]

    except SatelliteNotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to fetch satellite %s: %s", norad_id, e)
        raise DatabaseError(f"Failed to fetch satellite {norad_id}")


def list_satellites(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    List satellites with pagination.

    Args:
        limit: Max records to return (capped at 1000).
        offset: Starting offset.

    Returns:
        List of satellite row dicts.
    """
    limit = min(limit, 1000)  # Safety cap
    try:
        client = get_supabase_client()
        result = (
            client.table(TABLE)
            .select("*")
            .order("norad_id")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []

    except Exception as e:
        logger.error("Failed to list satellites: %s", e)
        raise DatabaseError("Failed to list satellites")


def count_satellites() -> int:
    """Return total satellite count."""
    try:
        client = get_supabase_client()
        result = (
            client.table(TABLE)
            .select("id", count="exact")
            .execute()
        )
        return result.count or 0
    except Exception as e:
        logger.error("Failed to count satellites: %s", e)
        raise DatabaseError("Failed to count satellites")
