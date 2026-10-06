"""CachePort adapters: bounded in-process TTL cache and Redis."""

import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from redis.exceptions import RedisError

from app.domain.clock import Clock, system_clock
from app.domain.ports import CachePort

logger = logging.getLogger(__name__)


class InMemoryCache(CachePort):
    """Single-process cache (default when REDIS_URL is unset)."""

    def __init__(self, clock: Clock = system_clock, max_entries: int = 1024):
        self._clock = clock
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[str, datetime]] = OrderedDict()

    async def get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._clock() >= expires_at:
            self._entries.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._entries[key] = (value, self._clock() + timedelta(seconds=ttl_seconds))
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._entries.pop(key, None)


class RedisCache(CachePort):
    """Shared cache across replicas. Redis outages degrade to cache misses."""

    _PREFIX = "cache:"

    def __init__(self, client: Any):
        self._client = client  # redis.asyncio.Redis (decode_responses=True)

    async def get(self, key: str) -> str | None:
        try:
            return await self._client.get(self._PREFIX + key)
        except RedisError:
            logger.warning("Redis cache GET failed; treating as miss", exc_info=True)
            return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            await self._client.set(self._PREFIX + key, value, ex=ttl_seconds)
        except RedisError:
            logger.warning("Redis cache SET failed; skipping", exc_info=True)

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self._client.delete(*(self._PREFIX + key for key in keys))
        except RedisError:
            logger.warning("Redis cache DELETE failed", exc_info=True)
