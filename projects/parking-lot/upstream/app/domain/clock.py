"""Clock port: the single source of "now" for use cases (testable)."""

from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    """Current instant as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
