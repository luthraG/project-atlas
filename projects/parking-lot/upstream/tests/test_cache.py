"""Cache port adapters, Redis limiter and cached repository decorators."""

from datetime import date, timedelta

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.domain.category import Category
from app.domain.login_attempts import LoginThrottlePolicy
from app.domain.report import RevenueReport
from app.domain.tariff import Tariff, TariffType
from app.infrastructure.cache import InMemoryCache, RedisCache
from app.infrastructure.cached_repositories import (
    CachedCategoryRepository,
    CachedReportRepository,
    CachedTariffRepository,
    ReportCachePolicy,
)
from app.infrastructure.redis_login_limiter import (
    RedisLoginAttemptLimiter,
    ResilientLoginAttemptLimiter,
)
from app.infrastructure.shared_resources import build_shared_resources

# --- InMemoryCache ------------------------------------------------------------


async def test_in_memory_cache_round_trip_and_ttl(clock):
    cache = InMemoryCache(clock=clock)
    await cache.set("k", "v", ttl_seconds=60)

    assert await cache.get("k") == "v"
    clock.advance(timedelta(seconds=61))
    assert await cache.get("k") is None


async def test_in_memory_cache_delete_many(clock):
    cache = InMemoryCache(clock=clock)
    await cache.set("a", "1", 60)
    await cache.set("b", "2", 60)

    await cache.delete("a", "b", "missing")

    assert await cache.get("a") is None and await cache.get("b") is None


async def test_in_memory_cache_is_bounded(clock):
    cache = InMemoryCache(clock=clock, max_entries=2)
    for key in ("a", "b", "c"):
        await cache.set(key, key, 60)

    assert await cache.get("a") is None
    assert await cache.get("c") == "c"


# --- RedisCache (fakeredis) ---------------------------------------------------


@pytest.fixture
def redis_client():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


async def test_redis_cache_round_trip(redis_client):
    cache = RedisCache(redis_client)
    await cache.set("k", "v", 60)

    assert await cache.get("k") == "v"
    assert 0 < await redis_client.ttl("cache:k") <= 60
    await cache.delete("k")
    assert await cache.get("k") is None


class _DownRedis:
    async def get(self, *_):
        raise RedisConnectionError("down")

    async def set(self, *_, **__):
        raise RedisConnectionError("down")

    async def delete(self, *_):
        raise RedisConnectionError("down")


async def test_redis_cache_degrades_to_miss_when_redis_is_down():
    cache = RedisCache(_DownRedis())

    await cache.set("k", "v", 60)

    assert await cache.get("k") is None


# --- Redis login limiter ------------------------------------------------------


def _limiter(redis_client, clock, max_failures=3):
    policy = LoginThrottlePolicy(max_failures=max_failures, window=timedelta(minutes=15))
    return RedisLoginAttemptLimiter(redis_client, clock=clock, policy=policy)


async def test_redis_limiter_locks_after_max_failures(redis_client, clock):
    limiter = _limiter(redis_client, clock)
    for _ in range(3):
        await limiter.record_failure("ip|ana")

    assert await limiter.retry_after_seconds("ip|ana") == 15 * 60
    assert await limiter.retry_after_seconds("ip|bob") == 0


async def test_redis_limiter_window_slides_and_reset_clears(redis_client, clock):
    limiter = _limiter(redis_client, clock)
    for _ in range(3):
        await limiter.record_failure("k")
    clock.advance(timedelta(minutes=16))

    assert await limiter.retry_after_seconds("k") == 0
    await limiter.record_failure("k")
    await limiter.reset("k")
    assert await redis_client.exists("login:fail:k") == 0


async def test_redis_limiter_keys_expire(redis_client, clock):
    limiter = _limiter(redis_client, clock)

    await limiter.record_failure("k")

    assert 0 < await redis_client.ttl("login:fail:k") <= 15 * 60


async def test_resilient_limiter_falls_back_when_redis_is_down(clock):
    from app.infrastructure.in_memory_login_limiter import InMemoryLoginAttemptLimiter
    from app.infrastructure.redis_login_limiter import ResilientLoginAttemptLimiter

    class _Down:
        async def record_failure(self, _):
            raise RedisConnectionError("down")

        async def retry_after_seconds(self, _):
            raise RedisConnectionError("down")

    policy = LoginThrottlePolicy(max_failures=1)
    fallback = InMemoryLoginAttemptLimiter(clock=clock, policy=policy)
    limiter = ResilientLoginAttemptLimiter(_Down(), fallback)

    await limiter.record_failure("k")

    assert await limiter.retry_after_seconds("k") > 0


def test_shared_resources_select_in_memory_without_redis_url():
    resources = build_shared_resources(None)

    assert isinstance(resources.cache, InMemoryCache)
    assert resources.redis is None


def test_shared_resources_select_redis_with_url():
    resources = build_shared_resources("redis://localhost:6399/0")

    assert isinstance(resources.cache, RedisCache)
    assert isinstance(resources.login_limiter, ResilientLoginAttemptLimiter)


# --- Cached repositories --------------------------------------------------------


class CountingTariffs:
    def __init__(self):
        self.rows = [Tariff(1, 1, TariffType.HOURLY, 3000, None, None)]
        self.list_calls = 0

    async def list_all(self):
        self.list_calls += 1
        return list(self.rows)

    async def list_by_category(self, category_id):
        self.list_calls += 1
        return [row for row in self.rows if row.category_id == category_id]

    async def get_by_id(self, tariff_id):
        return next((row for row in self.rows if row.id == tariff_id), None)

    async def create(self, tariff):
        tariff.id = len(self.rows) + 1
        self.rows.append(tariff)
        return tariff


async def test_cached_tariffs_hit_cache_and_round_trip_types(clock):
    inner = CountingTariffs()
    repo = CachedTariffRepository(inner, InMemoryCache(clock=clock))

    first = await repo.list_by_category(1)
    second = await repo.list_by_category(1)

    assert inner.list_calls == 1
    assert second == first
    assert second[0].type is TariffType.HOURLY


async def test_cached_tariffs_invalidate_on_write(clock):
    inner = CountingTariffs()
    repo = CachedTariffRepository(inner, InMemoryCache(clock=clock))
    await repo.list_all()
    await repo.list_by_category(1)

    await repo.create(Tariff(None, 1, TariffType.DAILY, 20000, None, None))

    assert len(await repo.list_all()) == 2
    assert len(await repo.list_by_category(1)) == 2


class CountingCategories:
    def __init__(self):
        self.rows = {1: Category(1, "carro")}
        self.calls = 0

    async def list_all(self):
        self.calls += 1
        return list(self.rows.values())

    async def get_by_id(self, category_id):
        self.calls += 1
        return self.rows.get(category_id)

    async def update(self, category):
        self.rows[category.id] = category
        return category


async def test_cached_categories_expire_and_invalidate(clock):
    inner = CountingCategories()
    repo = CachedCategoryRepository(inner, InMemoryCache(clock=clock))
    await repo.get_by_id(1)
    await repo.get_by_id(1)
    assert inner.calls == 1

    await repo.update(Category(1, "auto"))

    assert (await repo.get_by_id(1)).name == "auto"
    assert await repo.get_by_id(404) is None


class CountingReports:
    def __init__(self):
        self.calls = 0

    async def revenue_by_range(self, start_date, end_date):
        self.calls += 1
        return RevenueReport(total=self.calls)


async def test_past_revenue_ranges_are_cached_but_today_is_not(clock):
    from zoneinfo import ZoneInfo

    inner = CountingReports()
    policy = ReportCachePolicy(clock=clock, zone=ZoneInfo("America/Bogota"))
    repo = CachedReportRepository(inner, InMemoryCache(clock=clock), policy)
    today = clock.now.astimezone(ZoneInfo("America/Bogota")).date()
    past = date(2026, 3, 1)

    assert (await repo.revenue_by_range(past, past)).total == 1
    assert (await repo.revenue_by_range(past, past)).total == 1
    await repo.revenue_by_range(past, today)
    await repo.revenue_by_range(past, today)

    assert inner.calls == 3
