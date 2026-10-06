"""In-memory login attempt limiter tests (Success / Failure / Security)."""

from datetime import timedelta

from app.domain.login_attempts import LoginThrottlePolicy
from app.infrastructure.in_memory_login_limiter import InMemoryLoginAttemptLimiter


def _limiter(clock, **policy):
    return InMemoryLoginAttemptLimiter(clock=clock, policy=LoginThrottlePolicy(**policy))


async def test_not_locked_below_threshold(clock):
    limiter = _limiter(clock)
    for _ in range(4):
        await limiter.record_failure("ip|user")

    assert await limiter.retry_after_seconds("ip|user") == 0


async def test_locked_at_threshold_until_oldest_failure_leaves_window(clock):
    limiter = _limiter(clock)
    for _ in range(5):
        await limiter.record_failure("ip|user")
        clock.advance(timedelta(minutes=1))

    # oldest failure was 5 min ago -> 10 more minutes of lockout.
    assert await limiter.retry_after_seconds("ip|user") == 10 * 60


async def test_failures_outside_sliding_window_do_not_accumulate(clock):
    limiter = _limiter(clock)
    for _ in range(10):
        await limiter.record_failure("ip|user")
        clock.advance(timedelta(minutes=4))

    assert await limiter.retry_after_seconds("ip|user") == 0


async def test_reset_clears_failures(clock):
    limiter = _limiter(clock)
    for _ in range(5):
        await limiter.record_failure("ip|user")

    await limiter.reset("ip|user")

    assert await limiter.retry_after_seconds("ip|user") == 0


async def test_store_is_bounded_against_key_flooding(clock):
    """Security: random usernames must not grow memory without bound."""
    limiter = _limiter(clock, max_tracked_keys=100)
    for index in range(1000):
        await limiter.record_failure(f"ip|user-{index}")

    assert limiter.tracked_keys() <= 100
