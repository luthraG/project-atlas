"""Login throttling port and policy (brute-force protection for PIN login)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class LoginThrottlePolicy:
    max_failures: int = 5
    window: timedelta = timedelta(minutes=15)
    max_tracked_keys: int = 10_000


class LoginAttemptLimiter(ABC):
    """Sliding-window failure counter keyed by e.g. ``ip|username``.

    Implementations may be in-process (single worker) or shared (Redis).
    """

    @abstractmethod
    async def retry_after_seconds(self, key: str) -> int:
        """Seconds until ``key`` may try again; 0 when not locked."""

    @abstractmethod
    async def record_failure(self, key: str) -> None:
        """Register one failed attempt for ``key``."""

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Forget failures for ``key`` (after a successful login)."""
