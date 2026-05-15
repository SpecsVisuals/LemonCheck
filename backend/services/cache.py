"""
services/cache.py

Analysis result caching layer.

Caches DealReport results by a hash of the input (URL or VIN) to avoid
redundant Claude API calls for identical inputs within a time window.

Currently uses an in-memory dict (dev) with a TTL. In production, swap
the backend for Redis or a Supabase table.
"""

from typing import Optional

_cache: dict = {}

async def get_cached(key: str) -> Optional[dict]:
    # TODO: implement TTL-aware cache get
    return _cache.get(key)

async def set_cached(key: str, value: dict, ttl_seconds: int = 3600) -> None:
    # TODO: implement TTL-aware cache set
    _cache[key] = value
