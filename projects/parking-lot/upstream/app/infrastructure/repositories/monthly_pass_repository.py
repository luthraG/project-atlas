"""SQLAlchemy implementation of the monthly pass repository port."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.monthly_pass import MonthlyPass
from app.domain.pagination import Page, PageRequest
from app.domain.repositories import MonthlyPassRepository
from app.infrastructure.models import MonthlyPassModel
from app.infrastructure.repositories.paging import PagedQuery, fetch_page

_BY_ID = select(MonthlyPassModel).order_by(MonthlyPassModel.id)

class SqlAlchemyMonthlyPassRepository(MonthlyPassRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: MonthlyPassModel) -> MonthlyPass:
        return MonthlyPass(
            id=model.id,
            vehicle_id=model.vehicle_id,
            start_date=model.start_date,
            end_date=model.end_date,
            amount=model.amount,
            active=model.active,
        )

    async def get_by_id(self, pass_id: int) -> MonthlyPass | None:
        model = await self._session.get(MonthlyPassModel, pass_id)
        return self._to_entity(model) if model else None

    async def list_all(self) -> list[MonthlyPass]:
        result = await self._session.execute(
            select(MonthlyPassModel).order_by(MonthlyPassModel.id)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def list_by_vehicle(self, vehicle_id: int) -> list[MonthlyPass]:
        result = await self._session.execute(
            select(MonthlyPassModel)
            .where(MonthlyPassModel.vehicle_id == vehicle_id)
            .order_by(MonthlyPassModel.id)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def get_active_for_vehicle(
        self, vehicle_id: int, on_date: date
    ) -> MonthlyPass | None:
        result = await self._session.execute(
            select(MonthlyPassModel).where(
                MonthlyPassModel.vehicle_id == vehicle_id,
                MonthlyPassModel.active.is_(True),
                MonthlyPassModel.start_date <= on_date,
                MonthlyPassModel.end_date >= on_date,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_page(self, page: PageRequest) -> Page[MonthlyPass]:
        models, total = await fetch_page(self._session, PagedQuery(_BY_ID, page))
        return Page([self._to_entity(model) for model in models], total)

    async def create(self, monthly_pass: MonthlyPass) -> MonthlyPass:
        model = MonthlyPassModel(
            vehicle_id=monthly_pass.vehicle_id,
            start_date=monthly_pass.start_date,
            end_date=monthly_pass.end_date,
            amount=monthly_pass.amount,
            active=monthly_pass.active,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, monthly_pass: MonthlyPass) -> MonthlyPass:
        model = await self._session.get(MonthlyPassModel, monthly_pass.id)
        model.vehicle_id = monthly_pass.vehicle_id
        model.start_date = monthly_pass.start_date
        model.end_date = monthly_pass.end_date
        model.amount = monthly_pass.amount
        model.active = monthly_pass.active
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, pass_id: int) -> None:
        model = await self._session.get(MonthlyPassModel, pass_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
