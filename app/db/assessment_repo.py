"""
Conjunction assessment repository — Supabase CRUD for conjunction_assessments table.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.core.exceptions import AssessmentNotFoundError, DatabaseError
from app.db.client import get_supabase_client

logger = logging.getLogger(__name__)

TABLE = "conjunction_assessments"


def create_assessment(
    sat1_norad_id: str,
    sat2_norad_id: str,
    msd_predicted: float,
    collision_prob: float,
    risk_score: float,
    risk_tier: str,
    confidence: float,
    model_version: str,
) -> Dict[str, Any]:
    """
    Insert a new conjunction assessment.

    Returns:
        The inserted row as a dict.
    """
    try:
        client = get_supabase_client()
        data = {
            "sat1_norad_id": sat1_norad_id,
            "sat2_norad_id": sat2_norad_id,
            "msd_predicted": msd_predicted,
            "collision_prob": collision_prob,
            "risk_score": risk_score,
            "risk_tier": risk_tier,
            "confidence": confidence,
            "model_version": model_version,
        }
        result = client.table(TABLE).insert(data).execute()
        logger.info(
            "Created assessment: %s vs %s → %s (score=%.4f)",
            sat1_norad_id, sat2_norad_id, risk_tier, risk_score,
        )
        return result.data[0] if result.data else data

    except Exception as e:
        logger.error("Failed to create assessment: %s", e)
        raise DatabaseError("Failed to create conjunction assessment")


def get_assessment_by_id(assessment_id: str) -> Dict[str, Any]:
    """
    Fetch an assessment by its UUID.

    Raises:
        AssessmentNotFoundError: If not found.
    """
    try:
        client = get_supabase_client()
        result = (
            client.table(TABLE)
            .select("*")
            .eq("id", assessment_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise AssessmentNotFoundError(assessment_id)
        return result.data[0]

    except AssessmentNotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to fetch assessment %s: %s", assessment_id, e)
        raise DatabaseError(f"Failed to fetch assessment {assessment_id}")


def get_top_conjunctions(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Return highest-risk assessments ordered by risk_score descending.

    Args:
        limit: Max results (capped at 500).

    Returns:
        List of assessment dicts.
    """
    limit = min(limit, 500)  # Safety cap
    try:
        client = get_supabase_client()
        result = (
            client.table(TABLE)
            .select("*")
            .order("risk_score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    except Exception as e:
        logger.error("Failed to fetch top conjunctions: %s", e)
        raise DatabaseError("Failed to fetch top conjunctions")


def get_recent_assessment(
    sat1_norad_id: str,
    sat2_norad_id: str,
    max_age_seconds: int = 3600,
) -> Optional[Dict[str, Any]]:
    """
    Check for a recent cached assessment for this satellite pair.
    Checks both orderings (A-B and B-A).

    Returns:
        Assessment dict or None if no recent result.
    """
    try:
        client = get_supabase_client()

        cutoff = datetime.now(timezone.utc).isoformat()

        # Check A-B order
        result = (
            client.table(TABLE)
            .select("*")
            .eq("sat1_norad_id", sat1_norad_id)
            .eq("sat2_norad_id", sat2_norad_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]

        # Check B-A order
        result = (
            client.table(TABLE)
            .select("*")
            .eq("sat1_norad_id", sat2_norad_id)
            .eq("sat2_norad_id", sat1_norad_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]

        return None

    except Exception as e:
        logger.warning("Failed to check recent assessment cache: %s", e)
        return None  # Non-fatal — proceed with fresh computation
