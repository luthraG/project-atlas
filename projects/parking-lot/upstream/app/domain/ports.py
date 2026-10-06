"""Non-repository ports: security, cache and idempotency.

Implementations live in ``app.infrastructure``; the application layer only
sees these abstractions (injected by presentation providers).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class PasswordHasher(ABC):
    @abstractmethod
    async def hash(self, plain: str) -> str:
        """Return a salted hash of ``plain`` (CPU-bound: off the event loop)."""

    @abstractmethod
    async def verify(self, plain: str, hashed: str | None) -> bool:
        """True iff ``plain`` matches ``hashed``; None still costs one verify."""


class TokenIssuer(ABC):
    @abstractmethod
    def issue(self, subject: str) -> str:
        """Signed, expiring access token for ``subject``."""

    @abstractmethod
    def subject_of(self, token: str) -> str:
        """Verified subject; raises InvalidTokenError when invalid/expired."""


class CachePort(ABC):
    """Tiny string key/value cache with per-entry TTL (seconds)."""

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def delete(self, *keys: str) -> None: ...


PENDING_STATUS = 0  # reserved, response not recorded yet


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    user_id: int
    endpoint: str
    created_at: datetime
    status_code: int = PENDING_STATUS
    response_body: str = ""  # JSON document once completed

    @property
    def is_pending(self) -> bool:
        return self.status_code == PENDING_STATUS


class IdempotencyStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> IdempotencyRecord | None: ...

    @abstractmethod
    async def reserve(self, record: IdempotencyRecord) -> None:
        """Insert a pending record; IdempotencyKeyInUseError if the key exists."""

    @abstractmethod
    async def complete(self, record: IdempotencyRecord) -> None:
        """Store status/body on the previously reserved key."""

    @abstractmethod
    async def purge_older_than(self, cutoff: datetime) -> int:
        """Delete records created before ``cutoff``; returns rows removed."""
