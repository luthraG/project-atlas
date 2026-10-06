"""Vehicle use cases."""

from dataclasses import dataclass

from app.domain.errors import DuplicatePlateError, VehicleNotFoundError
from app.domain.pagination import Page, PageRequest
from app.domain.repositories import VehicleRepository
from app.domain.vehicle import Vehicle, normalize_plate

__all__ = ["DuplicatePlateError", "VehicleNotFoundError", "VehiclePatch", "VehicleService"]


@dataclass
class VehiclePatch:
    category_id: int | None = None
    color: str | None = None
    brand: str | None = None


class VehicleService:
    def __init__(self, vehicles: VehicleRepository):
        self._vehicles = vehicles

    async def create(self, vehicle: Vehicle) -> Vehicle:
        plate = normalize_plate(vehicle.plate)
        if await self._vehicles.get_by_plate(plate) is not None:
            raise DuplicatePlateError()
        vehicle.plate = plate
        return await self._vehicles.create(vehicle)

    async def list_page(self, page: PageRequest) -> Page[Vehicle]:
        return await self._vehicles.list_page(page)

    async def find_by_plate(self, plate: str) -> Vehicle | None:
        return await self._vehicles.get_by_plate(normalize_plate(plate))

    async def update(self, vehicle_id: int, patch: VehiclePatch) -> Vehicle:
        existing = await self._vehicles.get_by_id(vehicle_id)
        if existing is None:
            raise VehicleNotFoundError()
        if patch.category_id is not None:
            existing.category_id = patch.category_id
        if patch.color is not None:
            existing.color = patch.color
        if patch.brand is not None:
            existing.brand = patch.brand
        return await self._vehicles.update(existing)

    async def delete(self, vehicle_id: int) -> None:
        if await self._vehicles.get_by_id(vehicle_id) is None:
            raise VehicleNotFoundError()
        await self._vehicles.delete(vehicle_id)
