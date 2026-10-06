"""Monthly pass use cases with validation."""

from dataclasses import dataclass
from datetime import date

from app.domain.errors import MonthlyPassNotFoundError, VehicleNotFoundError
from app.domain.monthly_pass import MonthlyPass, validate_pass_dates
from app.domain.pagination import Page, PageRequest, paginate
from app.domain.repositories import MonthlyPassRepository, VehicleRepository

__all__ = [
    "MonthlyPassNotFoundError",
    "VehicleNotFoundError",
    "MonthlyPassPatch",
    "MonthlyPassService",
]


@dataclass
class MonthlyPassPatch:
    start_date: date | None = None
    end_date: date | None = None
    amount: int | None = None
    active: bool | None = None


class MonthlyPassService:
    def __init__(self, passes: MonthlyPassRepository, vehicles: VehicleRepository):
        self._passes = passes
        self._vehicles = vehicles

    async def create(self, monthly_pass: MonthlyPass) -> MonthlyPass:
        if await self._vehicles.get_by_id(monthly_pass.vehicle_id) is None:
            raise VehicleNotFoundError()
        validate_pass_dates(monthly_pass.start_date, monthly_pass.end_date)
        return await self._passes.create(monthly_pass)

    async def list_page(
        self, page: PageRequest, vehicle_id: int | None = None
    ) -> Page[MonthlyPass]:
        if vehicle_id is None:
            return await self._passes.list_page(page)
        return paginate(await self._passes.list_by_vehicle(vehicle_id), page)

    async def update(self, pass_id: int, patch: MonthlyPassPatch) -> MonthlyPass:
        existing = await self._passes.get_by_id(pass_id)
        if existing is None:
            raise MonthlyPassNotFoundError()
        merged = self._merge(existing, patch)
        validate_pass_dates(merged.start_date, merged.end_date)
        return await self._passes.update(merged)

    async def delete(self, pass_id: int) -> None:
        if await self._passes.get_by_id(pass_id) is None:
            raise MonthlyPassNotFoundError()
        await self._passes.delete(pass_id)

    def _merge(self, existing: MonthlyPass, patch: MonthlyPassPatch) -> MonthlyPass:
        return MonthlyPass(
            id=existing.id,
            vehicle_id=existing.vehicle_id,
            start_date=patch.start_date if patch.start_date is not None else existing.start_date,
            end_date=patch.end_date if patch.end_date is not None else existing.end_date,
            amount=patch.amount if patch.amount is not None else existing.amount,
            active=patch.active if patch.active is not None else existing.active,
        )
