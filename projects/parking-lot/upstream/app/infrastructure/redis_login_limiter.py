"""Redis-backed sliding-window login limiter (shared across replicas).

One sorted set per throttle key: members are failure events scored by their
UNIX timestamp; entries older than the window are trimmed on every access
and the key expires with the window, so memory stays bounded.
"""

import logging
import uuid
from math import ceil
from typing import Any

from redis.exceptions import RedisError

from app.domain.clock import Clock, system_clock
from app.domain.login_attempts import LoginAttemptLimiter, LoginThrottlePolicy

logger = logging.getLogger(__name__)


class RedisLoginAttemptLimiter(LoginAttemptLimiter):
    _PREFIX = "login:fail:"

    def __init__(
        self, client: Any, clock: Clock = system_clock, policy: LoginThrottlePolicy | None = None
    ):
        self._client = client
        self._clock = clock
        self._policy = policy or LoginThrottlePolicy()

    async def retry_after_seconds(self, key: str) -> int:
        redis_key, now = self._PREFIX + key, self._now()
        await self._client.zremrangebyscore(redis_key, "-inf", now - self._window())
        limit = self._policy.max_failures
        oldest_counted = await self._client.zrange(redis_key, -limit, -limit, withscores=True)
        if await self._client.zcard(redis_key) < limit or not oldest_counted:
            return 0
        unlock_at = oldest_counted[0][1] + self._window()
        return max(ceil(unlock_at - now), 1)

    async def record_failure(self, key: str) -> None:
        redis_key, now = self._PREFIX + key, self._now()
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, "-inf", now - self._window())
            pipe.zadd(redis_key, {uuid.uuid4().hex: now})
            pipe.expire(redis_key, ceil(self._window()))
            await pipe.execute()

    async def reset(self, key: str) -> None:
        await self._client.delete(self._PREFIX + key)

    def _now(self) -> float:
        return self._clock().timestamp()

    def _window(self) -> float:
        return self._policy.window.total_seconds()


class ResilientLoginAttemptLimiter(LoginAttemptLimiter):
    """Use Redis; on a Redis outage fall back to the in-process limiter.

    Keeps brute-force protection (per replica) instead of failing logins
    with 500 or silently disabling throttling.
    """

    def __init__(self, primary: LoginAttemptLimiter, fallback: LoginAttemptLimiter):
        self._primary = primary
        self._fallback = fallback

    async def retry_after_seconds(self, key: str) -> int:
        return await self._call("retry_after_seconds", key)

    async def record_failure(self, key: str) -> None:
        await self._call("record_failure", key)

    async def reset(self, key: str) -> None:
        await self._call("reset", key)

    async def _call(self, method: str, key: str):
        try:
            return await getattr(self._primary, method)(key)
        except RedisError:
            logger.warning("Redis limiter unavailable; using in-process fallback")
            return await getattr(self._fallback, method)(key)
