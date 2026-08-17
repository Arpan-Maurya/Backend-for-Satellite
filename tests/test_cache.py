"""
Tests for in-memory TTL cache.
"""

import time
import pytest
from app.core.cache import InMemoryTTLCache


def test_cache_set_and_get():
    cache = InMemoryTTLCache(max_size=5, default_ttl_seconds=2)
    cache.set("key1", "val1")
    assert cache.get("key1") == "val1"
    assert cache.size() == 1


def test_cache_miss():
    cache = InMemoryTTLCache()
    assert cache.get("nonexistent") is None


def test_cache_expiration():
    cache = InMemoryTTLCache(default_ttl_seconds=1)
    cache.set("temp", "data", ttl_seconds=1)
    assert cache.get("temp") == "data"
    time.sleep(1.05)
    assert cache.get("temp") is None


def test_cache_capacity_eviction():
    cache = InMemoryTTLCache(max_size=2, default_ttl_seconds=10)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")  # Should evict k1
    assert cache.size() == 2
    assert cache.get("k1") is None
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"


def test_cache_clear():
    cache = InMemoryTTLCache()
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.clear()
    assert cache.size() == 0
    assert cache.get("k1") is None
