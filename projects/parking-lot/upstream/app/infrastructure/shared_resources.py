"""Process-wide adapters chosen at startup from configuration.

Without ``REDIS_URL`` everything is in-process (single worker). With it, the
cache and the login limiter are shared through Redis so several replicas /
workers see the same state.
"""

from dataclasses import dataclass
from typing import Any

from redis import asyncio as redis_asyncio

from app.domain.login_attempts import LoginAttemptLimiter
from app.domain.ports import CachePort
from app.infrastructure.cache import InMemoryCache, RedisCache
from app.infrastructure.in_memory_login_limiter import InMemoryLoginAttemptLimiter
from app.infrastructure.redis_login_limiter import (
    RedisLoginAttemptLimiter,
    ResilientLoginAttemptLimiter,
)


@dataclass
class SharedResources:
    cache: CachePort
    login_limiter: LoginAttemptLimiter
    redis: Any | None = None

    @property
    def backend(self) -> str:
        return "redis" if self.redis is not None else "memory"

    async def aclose(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()


def build_shared_resources(redis_url: str | None) -> SharedResources:
    if not redis_url:
        return SharedResources(InMemoryCache(), InMemoryLoginAttemptLimiter())
    client = redis_asyncio.from_url(
        redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
    )
    limiter = ResilientLoginAttemptLimiter(
        RedisLoginAttemptLimiter(client), InMemoryLoginAttemptLimiter()
    )
    return SharedResources(RedisCache(client), limiter, client)
