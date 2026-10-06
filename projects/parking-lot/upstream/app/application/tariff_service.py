"""Tariff use cases with validation."""

from dataclasses import dataclass

from app.domain.errors import TariffNotFoundError
from app.domain.pagination import Page, PageRequest, paginate
from app.domain.repositories import TariffRepository
from app.domain.tariff import (
    Tariff,
    TariffType,
    validate_amount,
    validate_time,
    validate_window,
)

__all__ = ["TariffNotFoundError", "TariffPatch", "TariffService"]


@dataclass
class TariffPatch:
    type: TariffType | None = None
    amount: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    active: bool | None = None


class TariffService:
    def __init__(self, tariffs: TariffRepository):
        self._tariffs = tariffs

    async def create(self, tariff: Tariff) -> Tariff:
        self._validate(tariff)
        return await self._tariffs.create(tariff)

    async def list_all(self) -> list[Tariff]:
        return await self._tariffs.list_all()

    async def list_by_category(self, category_id: int) -> list[Tariff]:
        return await self._tariffs.list_by_category(category_id)

    async def list_page(self, page: PageRequest, category_id: int | None = None) -> Page[Tariff]:
        rows = (
            await self.list_by_category(category_id)
            if category_id is not None
            else await self.list_all()
        )
        return paginate(rows, page)

    async def update(self, tariff_id: int, patch: TariffPatch) -> Tariff:
        existing = await self._tariffs.get_by_id(tariff_id)
        if existing is None:
            raise TariffNotFoundError()
        merged = self._merge(existing, patch)
        self._validate(merged)
        return await self._tariffs.update(merged)

    async def delete(self, tariff_id: int) -> None:
        if await self._tariffs.get_by_id(tariff_id) is None:
            raise TariffNotFoundError()
        await self._tariffs.delete(tariff_id)

    def _merge(self, existing: Tariff, patch: TariffPatch) -> Tariff:
        return Tariff(
            id=existing.id,
            category_id=existing.category_id,
            type=patch.type if patch.type is not None else existing.type,
            amount=patch.amount if patch.amount is not None else existing.amount,
            start_time=patch.start_time if patch.start_time is not None else existing.start_time,
            end_time=patch.end_time if patch.end_time is not None else existing.end_time,
            active=patch.active if patch.active is not None else existing.active,
        )

    def _validate(self, tariff: Tariff) -> None:
        validate_amount(tariff.amount)
        validate_time(tariff.start_time)
        validate_time(tariff.end_time)
        validate_window(tariff.type, tariff.start_time, tariff.end_time)
