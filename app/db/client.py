"""
Supabase client singleton.

Creates a SINGLE Supabase client using the service-role key.
This key must NEVER be exposed to the frontend.
"""

import logging
from typing import Optional

from supabase import create_client, Client

from app.config import get_settings

logger = logging.getLogger(__name__)

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create the singleton Supabase client.

    Uses the service-role key for full database access (bypasses RLS).
    This client is server-side only.

    Returns:
        Supabase Client instance.

    Raises:
        RuntimeError: If Supabase URL or key is not configured.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    settings = get_settings()

    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL not configured")
    if not settings.supabase_service_key:
        raise RuntimeError("SUPABASE_SERVICE_KEY not configured")

    logger.info("Initializing Supabase client for %s", settings.supabase_url)
    _supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)

    return _supabase_client


def reset_client() -> None:
    """Reset the client (useful for testing)."""
    global _supabase_client
    _supabase_client = None
