"""
Risk alerts repository — Supabase CRUD for risk_alerts table.
"""

import logging
from typing import List, Dict, Any

from app.core.exceptions import DatabaseError
from app.db.client import get_supabase_client

logger = logging.getLogger(__name__)

TABLE = "risk_alerts"


def create_alert(
    sat1_norad_id: str,
    sat2_norad_id: str,
    risk_tier: str,
    message: str = "",
) -> Dict[str, Any]:
    """
    Insert a new risk alert for HIGH or CRITICAL conjunctions.

    Returns:
        The inserted alert row.
    """
    try:
        client = get_supabase_client()
        data = {
            "sat1_norad_id": sat1_norad_id,
            "sat2_norad_id": sat2_norad_id,
            "risk_tier": risk_tier,
            "message": message,
        }
        result = client.table(TABLE).insert(data).execute()
        logger.info(
            "Alert created: %s vs %s → %s",
            sat1_norad_id, sat2_norad_id, risk_tier,
        )
        return result.data[0] if result.data else data

    except Exception as e:
        logger.error("Failed to create alert: %s", e)
        raise DatabaseError("Failed to create risk alert")


def list_alerts(
    risk_tier: str = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    List alerts, optionally filtered by tier.

    Args:
        risk_tier: Optional filter (HIGH, CRITICAL, etc.)
        limit: Max results (capped at 500).

    Returns:
        List of alert dicts.
    """
    limit = min(limit, 500)
    try:
        client = get_supabase_client()
        query = client.table(TABLE).select("*").order("created_at", desc=True).limit(limit)
        if risk_tier:
            query = query.eq("risk_tier", risk_tier)
        result = query.execute()
        return result.data or []

    except Exception as e:
        logger.error("Failed to list alerts: %s", e)
        raise DatabaseError("Failed to list risk alerts")
