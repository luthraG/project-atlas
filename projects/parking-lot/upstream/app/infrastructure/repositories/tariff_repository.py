"""SQLAlchemy implementation of the tariff repository port."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories import TariffRepository
from app.domain.tariff import Tariff, TariffType
from app.infrastructure.models import TariffModel


class SqlAlchemyTariffRepository(TariffRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: TariffModel) -> Tariff:
        return Tariff(
            id=model.id,
            category_id=model.category_id,
            type=TariffType(model.type),
            amount=model.amount,
            start_time=model.start_time,
            end_time=model.end_time,
            active=model.active,
        )

    async def get_by_id(self, tariff_id: int) -> Tariff | None:
        model = await self._session.get(TariffModel, tariff_id)
        return self._to_entity(model) if model else None

    async def list_all(self) -> list[Tariff]:
        result = await self._session.execute(select(TariffModel).order_by(TariffModel.id))
        return [self._to_entity(model) for model in result.scalars()]

    async def list_by_category(self, category_id: int) -> list[Tariff]:
        result = await self._session.execute(
            select(TariffModel)
            .where(TariffModel.category_id == category_id)
            .order_by(TariffModel.id)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def create(self, tariff: Tariff) -> Tariff:
        model = TariffModel(
            category_id=tariff.category_id,
            type=tariff.type.value,
            amount=tariff.amount,
            start_time=tariff.start_time,
            end_time=tariff.end_time,
            active=tariff.active,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, tariff: Tariff) -> Tariff:
        model = await self._session.get(TariffModel, tariff.id)
        model.type = tariff.type.value
        model.amount = tariff.amount
        model.start_time = tariff.start_time
        model.end_time = tariff.end_time
        model.active = tariff.active
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, tariff_id: int) -> None:
        model = await self._session.get(TariffModel, tariff_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
