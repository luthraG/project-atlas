"""Check-out use case: close an open parking session and charge its fare."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.billing_service import FareService, StayQuery
from app.application.commands import CheckOutCommand
from app.domain.billing import FareCalculator
from app.domain.clock import Clock, system_clock
from app.domain.errors import (
    InvalidExitTimeError,
    SessionAlreadyClosedError,
    SessionNotFoundError,
    VehicleNotFoundError,
)
from app.domain.parking_session import ParkingSession, SessionStatus
from app.domain.repositories import (
    MonthlyPassRepository,
    ParkingSessionRepository,
    TariffRepository,
    VehicleRepository,
)
from app.domain.vehicle import Vehicle

__all__ = [
    "CheckOutContext",
    "CheckOutRepositories",
    "CheckOutService",
    "ClosedSession",
    "InvalidExitTimeError",
    "SessionAlreadyClosedError",
    "SessionNotFoundError",
]

# Tolerated client clock drift for offline-queued check-outs.
MAX_CLIENT_CLOCK_SKEW = timedelta(minutes=5)


@dataclass
class CheckOutRepositories:
    sessions: ParkingSessionRepository
    vehicles: VehicleRepository
    tariffs: TariffRepository
    monthly_passes: MonthlyPassRepository


@dataclass(frozen=True)
class CheckOutContext:
    calculator: FareCalculator
    clock: Clock = system_clock


@dataclass(frozen=True)
class ClosedSession:
    session: ParkingSession
    vehicle: Vehicle


class CheckOutService:
    def __init__(self, repos: CheckOutRepositories, context: CheckOutContext):
        self._repos = repos
        self._context = context

    async def close_session(self, command: CheckOutCommand) -> ClosedSession:
        session = await self._open_session(command.session_id)
        vehicle = await self._vehicle_of(session)
        session.exit_time = self._resolve_exit_time(session.entry_time, command.client_exit_time)
        session.amount_charged = await self._fare_for(session, vehicle)
        session.status = SessionStatus.CLOSED
        session.ticket_number = f"TCK-{session.id:06d}"
        closed = await self._repos.sessions.close(session)
        if closed is None:  # lost a concurrent check-out race
            raise SessionAlreadyClosedError()
        return ClosedSession(closed, vehicle)

    async def _open_session(self, session_id: int) -> ParkingSession:
        session = await self._repos.sessions.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundError()
        if session.status == SessionStatus.CLOSED:
            raise SessionAlreadyClosedError()
        return session

    async def _vehicle_of(self, session: ParkingSession) -> Vehicle:
        vehicle = await self._repos.vehicles.get_by_id(session.vehicle_id)
        if vehicle is None:
            raise VehicleNotFoundError()
        return vehicle

    def _resolve_exit_time(self, entry_time: datetime, client: datetime | None) -> datetime:
        now = self._context.clock()
        exit_time = client or now
        if client is not None and client.tzinfo is None:
            raise InvalidExitTimeError("client_exit_time must include a timezone offset")
        if not entry_time < exit_time <= now + MAX_CLIENT_CLOCK_SKEW:
            raise InvalidExitTimeError(
                "client_exit_time must be after entry_time and at most "
                "5 minutes in the future"
            )
        return exit_time.astimezone(UTC)

    async def _fare_for(self, session: ParkingSession, vehicle: Vehicle) -> int:
        calculator = self._context.calculator
        active_pass = await self._repos.monthly_passes.get_active_for_vehicle(
            vehicle.id, calculator.local_date(session.exit_time)
        )
        query = StayQuery(vehicle.category_id, session.entry_time, session.exit_time,
                          has_active_monthly_pass=active_pass is not None)
        amount = await FareService(self._repos.tariffs, calculator).quote(query)
        return round(amount)
