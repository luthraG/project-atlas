"""SQLAlchemy implementation of the parking session repository port."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DuplicateOpenSessionError
from app.domain.pagination import Page, PageRequest
from app.domain.parking_session import ParkingSession, SessionStatus
from app.domain.repositories import ParkingSessionRepository
from app.infrastructure.models import ParkingSessionModel
from app.infrastructure.repositories.paging import PagedQuery, fetch_page


def _as_utc(value: datetime | None) -> datetime | None:
    # SQLite (used by the test suite) does not persist tzinfo on
    # DateTime(timezone=True) columns, so values round-trip as naive even
    # though every timestamp in this codebase is written in UTC. Normalize
    # on read so callers can always compare/subtract these safely.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


_OPEN_BY_ENTRY = (
    select(ParkingSessionModel)
    .where(ParkingSessionModel.status == SessionStatus.OPEN.value)
    .order_by(ParkingSessionModel.entry_time, ParkingSessionModel.id)
)

class SqlAlchemyParkingSessionRepository(ParkingSessionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: ParkingSessionModel) -> ParkingSession:
        return ParkingSession(
            id=model.id,
            vehicle_id=model.vehicle_id,
            operator_id=model.operator_id,
            entry_time=_as_utc(model.entry_time),
            status=SessionStatus(model.status),
            exit_time=_as_utc(model.exit_time),
            amount_charged=model.amount_charged,
            ticket_number=model.ticket_number,
        )

    async def get_by_id(self, session_id: int) -> ParkingSession | None:
        model = await self._session.get(ParkingSessionModel, session_id)
        return self._to_entity(model) if model else None

    async def get_open_by_vehicle_id(
        self, vehicle_id: int
    ) -> ParkingSession | None:
        result = await self._session.execute(
            select(ParkingSessionModel).where(
                ParkingSessionModel.vehicle_id == vehicle_id,
                ParkingSessionModel.status == SessionStatus.OPEN.value,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_open(self) -> list[ParkingSession]:
        result = await self._session.execute(_OPEN_BY_ENTRY)
        return [self._to_entity(model) for model in result.scalars()]

    async def list_open_page(self, page: PageRequest) -> Page[ParkingSession]:
        models, total = await fetch_page(self._session, PagedQuery(_OPEN_BY_ENTRY, page))
        return Page([self._to_entity(model) for model in models], total)

    async def create(self, session: ParkingSession) -> ParkingSession:
        model = ParkingSessionModel(
            vehicle_id=session.vehicle_id,
            operator_id=session.operator_id,
            entry_time=session.entry_time,
            status=session.status.value,
        )
        # uq_open_session_per_vehicle is the source of truth under races.
        try:
            async with self._session.begin_nested():
                self._session.add(model)
        except IntegrityError as exc:
            raise DuplicateOpenSessionError() from exc
        return self._to_entity(model)

    async def update(self, session: ParkingSession) -> ParkingSession:
        model = await self._session.get(ParkingSessionModel, session.id)
        model.status = session.status.value
        model.exit_time = session.exit_time
        model.amount_charged = session.amount_charged
        model.ticket_number = session.ticket_number
        await self._session.flush()
        return self._to_entity(model)

    async def close(self, session: ParkingSession) -> ParkingSession | None:
        # Compare-and-set on status: of two concurrent check-outs exactly one
        # matches the WHERE clause; the loser sees rowcount 0.
        result = await self._session.execute(
            update(ParkingSessionModel)
            .where(
                ParkingSessionModel.id == session.id,
                ParkingSessionModel.status == SessionStatus.OPEN.value,
            )
            .values(
                status=SessionStatus.CLOSED.value,
                exit_time=session.exit_time,
                amount_charged=session.amount_charged,
                ticket_number=session.ticket_number,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            return None
        return await self._refetch(session.id)

    async def _refetch(self, session_id: int) -> ParkingSession:
        model = await self._session.get(
            ParkingSessionModel, session_id, populate_existing=True
        )
        return self._to_entity(model)
