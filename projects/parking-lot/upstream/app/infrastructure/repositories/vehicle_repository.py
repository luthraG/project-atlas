"""SQLAlchemy implementation of the vehicle repository port."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DuplicatePlateError
from app.domain.pagination import Page, PageRequest
from app.domain.repositories import VehicleRepository
from app.domain.vehicle import Vehicle
from app.infrastructure.models import VehicleModel
from app.infrastructure.repositories.paging import PagedQuery, fetch_page

_BY_PLATE = select(VehicleModel).order_by(VehicleModel.plate)

class SqlAlchemyVehicleRepository(VehicleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: VehicleModel) -> Vehicle:
        return Vehicle(
            id=model.id,
            plate=model.plate,
            category_id=model.category_id,
            color=model.color,
            brand=model.brand,
            created_by=model.created_by,
        )

    async def get_by_id(self, vehicle_id: int) -> Vehicle | None:
        model = await self._session.get(VehicleModel, vehicle_id)
        return self._to_entity(model) if model else None

    async def get_by_plate(self, plate: str) -> Vehicle | None:
        result = await self._session.execute(
            select(VehicleModel).where(VehicleModel.plate == plate)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_ids(self, vehicle_ids: list[int]) -> list[Vehicle]:
        result = await self._session.execute(
            select(VehicleModel).where(VehicleModel.id.in_(vehicle_ids))
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def list_all(self) -> list[Vehicle]:
        result = await self._session.execute(
            select(VehicleModel).order_by(VehicleModel.plate)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def list_page(self, page: PageRequest) -> Page[Vehicle]:
        models, total = await fetch_page(self._session, PagedQuery(_BY_PLATE, page))
        return Page([self._to_entity(model) for model in models], total)

    async def create(self, vehicle: Vehicle) -> Vehicle:
        model = VehicleModel(
            plate=vehicle.plate,
            category_id=vehicle.category_id,
            color=vehicle.color,
            brand=vehicle.brand,
            created_by=vehicle.created_by,
        )
        # SAVEPOINT: a unique-plate race rolls back only this insert, so the
        # caller can re-read the winner's row and keep the transaction.
        try:
            async with self._session.begin_nested():
                self._session.add(model)
        except IntegrityError as exc:
            raise DuplicatePlateError() from exc
        return self._to_entity(model)

    async def update(self, vehicle: Vehicle) -> Vehicle:
        model = await self._session.get(VehicleModel, vehicle.id)
        model.color = vehicle.color
        model.brand = vehicle.brand
        model.category_id = vehicle.category_id
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, vehicle_id: int) -> None:
        model = await self._session.get(VehicleModel, vehicle_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
