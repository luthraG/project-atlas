"""Read-through cache decorators over repository ports (OCP: services unchanged).

Catalog reads (tariffs, categories) are cached for ``ttl`` seconds and
invalidated on every write through the decorator. Invalidation happens at
write time (before commit), so a concurrent reader may re-cache the old
value for at most one TTL. Revenue reports are cached only for ranges that
end before the current business-local day.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.category import Category
from app.domain.clock import Clock, system_clock
from app.domain.ports import CachePort
from app.domain.report import CategoryRevenue, DailyRevenue, OccupancyReport, RevenueReport
from app.domain.repositories import CategoryRepository, ReportRepository, TariffRepository
from app.domain.tariff import Tariff, TariffType

CATALOG_TTL_SECONDS = 60


@dataclass(frozen=True)
class _Cached:
    cache: CachePort
    ttl: int

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        """JSON-decoded cached value, or ``loader()`` (stored when not None)."""
        raw = await self.cache.get(key)
        if raw is not None:
            return json.loads(raw)
        value = await loader()
        if value is not None:
            await self.cache.set(key, json.dumps(value), self.ttl)
        return value


def _tariff_from(data: dict) -> Tariff:
    return Tariff(**{**data, "type": TariffType(data["type"])})


def _tariff_rows(rows: list[Tariff]) -> list[dict]:
    return [{**asdict(row), "type": row.type.value} for row in rows]


class CachedTariffRepository(TariffRepository):
    def __init__(self, inner: TariffRepository, cache: CachePort,
                 ttl: int = CATALOG_TTL_SECONDS):
        self._inner = inner
        self._cached = _Cached(cache, ttl)

    async def get_by_id(self, tariff_id: int) -> Tariff | None:
        return await self._inner.get_by_id(tariff_id)

    async def list_all(self) -> list[Tariff]:
        rows = await self._cached.get_or_load(
            "tariffs:all", lambda: self._load(self._inner.list_all()))
        return [_tariff_from(row) for row in rows]

    async def list_by_category(self, category_id: int) -> list[Tariff]:
        rows = await self._cached.get_or_load(
            f"tariffs:category:{category_id}",
            lambda: self._load(self._inner.list_by_category(category_id)),
        )
        return [_tariff_from(row) for row in rows]

    async def create(self, tariff: Tariff) -> Tariff:
        created = await self._inner.create(tariff)
        await self._invalidate(created.category_id)
        return created

    async def update(self, tariff: Tariff) -> Tariff:
        updated = await self._inner.update(tariff)
        await self._invalidate(updated.category_id)
        return updated

    async def delete(self, tariff_id: int) -> None:
        existing = await self._inner.get_by_id(tariff_id)
        await self._inner.delete(tariff_id)
        if existing is not None:
            await self._invalidate(existing.category_id)

    @staticmethod
    async def _load(rows: Awaitable[list[Tariff]]) -> list[dict]:
        return _tariff_rows(await rows)

    async def _invalidate(self, category_id: int) -> None:
        await self._cached.cache.delete("tariffs:all", f"tariffs:category:{category_id}")


class CachedCategoryRepository(CategoryRepository):
    def __init__(self, inner: CategoryRepository, cache: CachePort,
                 ttl: int = CATALOG_TTL_SECONDS):
        self._inner = inner
        self._cached = _Cached(cache, ttl)

    async def get_by_name(self, name: str) -> Category | None:
        # Uniqueness checks must always hit the database.
        return await self._inner.get_by_name(name)

    async def get_by_id(self, category_id: int) -> Category | None:
        data = await self._cached.get_or_load(
            f"categories:id:{category_id}", lambda: self._load_one(category_id))
        return Category(**data) if data is not None else None

    async def list_all(self) -> list[Category]:
        rows = await self._cached.get_or_load("categories:all", self._load_all)
        return [Category(**row) for row in rows]

    async def create(self, category: Category) -> Category:
        created = await self._inner.create(category)
        await self._invalidate(created.id)
        return created

    async def update(self, category: Category) -> Category:
        updated = await self._inner.update(category)
        await self._invalidate(updated.id)
        return updated

    async def delete(self, category_id: int) -> None:
        await self._inner.delete(category_id)
        await self._invalidate(category_id)

    async def _load_one(self, category_id: int) -> dict | None:
        category = await self._inner.get_by_id(category_id)
        return asdict(category) if category is not None else None

    async def _load_all(self) -> list[dict]:
        return [asdict(category) for category in await self._inner.list_all()]

    async def _invalidate(self, category_id: int | None) -> None:
        await self._cached.cache.delete("categories:all", f"categories:id:{category_id}")


@dataclass(frozen=True)
class ReportCachePolicy:
    zone: ZoneInfo
    clock: Clock = system_clock
    # Offline check-outs may still land in past days (client_exit_time), so
    # past ranges are near-immutable rather than immutable: keep a short TTL.
    ttl: int = 600

    def is_cacheable(self, end_date: date) -> bool:
        return end_date < self.clock().astimezone(self.zone).date()


def _revenue_from(data: dict) -> RevenueReport:
    return RevenueReport(
        total=data["total"],
        by_day=[DailyRevenue(**day) for day in data["by_day"]],
        by_category=[CategoryRevenue(**row) for row in data["by_category"]],
    )


class CachedReportRepository(ReportRepository):
    def __init__(self, inner: ReportRepository, cache: CachePort, policy: ReportCachePolicy):
        self._inner = inner
        self._cached = _Cached(cache, policy.ttl)
        self._policy = policy

    async def revenue_by_range(self, start_date: date, end_date: date) -> RevenueReport:
        if not self._policy.is_cacheable(end_date):
            return await self._inner.revenue_by_range(start_date, end_date)
        data = await self._cached.get_or_load(
            f"report:revenue:{start_date.isoformat()}:{end_date.isoformat()}",
            lambda: self._load(start_date, end_date),
        )
        return _revenue_from(data)

    async def current_occupancy(self) -> OccupancyReport:
        return await self._inner.current_occupancy()

    async def _load(self, start_date: date, end_date: date) -> dict:
        return asdict(await self._inner.revenue_by_range(start_date, end_date))
