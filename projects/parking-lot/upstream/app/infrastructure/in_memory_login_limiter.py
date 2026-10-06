"""In-process sliding-window login limiter.

State lives in this worker's memory: correct for the single-worker
deployment; swap for a Redis-backed LoginAttemptLimiter when scaling out.
"""

from collections import OrderedDict, deque
from datetime import datetime
from math import ceil

from app.domain.clock import Clock, system_clock
from app.domain.login_attempts import LoginAttemptLimiter, LoginThrottlePolicy


class InMemoryLoginAttemptLimiter(LoginAttemptLimiter):
    def __init__(
        self, clock: Clock = system_clock, policy: LoginThrottlePolicy | None = None
    ):
        self._clock = clock
        self._policy = policy or LoginThrottlePolicy()
        self._failures: OrderedDict[str, deque[datetime]] = OrderedDict()

    async def retry_after_seconds(self, key: str) -> int:
        failures = self._recent_failures(key)
        if len(failures) < self._policy.max_failures:
            return 0
        unlock_at = failures[-self._policy.max_failures] + self._policy.window
        return max(ceil((unlock_at - self._clock()).total_seconds()), 1)

    async def record_failure(self, key: str) -> None:
        failures = self._recent_failures(key)
        failures.append(self._clock())
        self._failures[key] = failures
        self._failures.move_to_end(key)
        self._evict_overflow()

    async def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def tracked_keys(self) -> int:
        return len(self._failures)

    def _recent_failures(self, key: str) -> deque[datetime]:
        failures = self._failures.get(key, deque())
        cutoff = self._clock() - self._policy.window
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
        return failures

    def _evict_overflow(self) -> None:
        # Bounded memory: drop least-recently-failed keys first.
        while len(self._failures) > self._policy.max_tracked_keys:
            self._failures.popitem(last=False)
