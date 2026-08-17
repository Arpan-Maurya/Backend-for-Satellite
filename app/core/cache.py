"""
Lightweight in-memory TTL cache for orbital computations and TLE lookups.
Bounded size and time-to-live prevent memory growth and stale state.
"""

import time
import threading
from typing import Any, Optional, Dict, Tuple


class InMemoryTTLCache:
    """Thread-safe bounded in-memory cache with Time-To-Live (TTL) expiration."""

    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 300) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expire_timestamp)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item if present and not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            value, expire_time = self._cache[key]
            if time.time() > expire_time:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store item with TTL expiration."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expire_time = time.time() + ttl

        with self._lock:
            # Evict oldest entry if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = (value, expire_time)

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Current number of cached entries."""
        with self._lock:
            return len(self._cache)


# Global cache instance for orbital/assessment results
orbital_cache = InMemoryTTLCache(max_size=1000, default_ttl_seconds=300)
