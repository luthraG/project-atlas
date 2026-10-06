"""Parking session repository tests (Success / Failure / Security)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.category import Category
from app.domain.errors import DuplicateOpenSessionError
from app.domain.parking_session import ParkingSession, SessionStatus
from app.domain.user import User, UserRole
from app.domain.vehicle import Vehicle
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.parking_session_repository import (
    SqlAlchemyParkingSessionRepository,
)
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.repositories.vehicle_repository import (
    SqlAlchemyVehicleRepository,
)

NOW = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)


@pytest.fixture
async def vehicle_id(session_factory):
    async with session_factory() as session:
        category_repository = SqlAlchemyCategoryRepository(session)
        category = await category_repository.create(Category(id=None, name="carro"))
        vehicle_repository = SqlAlchemyVehicleRepository(session)
        vehicle = await vehicle_repository.create(
            Vehicle(id=None, plate="ABC123", category_id=category.id)
        )
        await session.commit()
        return vehicle.id


@pytest.fixture
async def operator_id(session_factory):
    async with session_factory() as session:
        user_repository = SqlAlchemyUserRepository(session)
        user = await user_repository.create(
            User(
                id=None,
                username="operator",
                display_name="Operator",
                role=UserRole.OPERATOR,
                pin_hash="hash",
            )
        )
        await session.commit()
        return user.id


@pytest.fixture
async def repository(session_factory):
    async with session_factory() as session:
        yield SqlAlchemyParkingSessionRepository(session)


async def test_create_and_get_open_by_vehicle_id(repository, vehicle_id, operator_id):
    session = await repository.create(
        ParkingSession(
            id=None,
            vehicle_id=vehicle_id,
            operator_id=operator_id,
            entry_time=NOW,
        )
    )

    fetched = await repository.get_open_by_vehicle_id(vehicle_id)

    assert fetched is not None
    assert fetched.id == session.id
    assert fetched.status == SessionStatus.OPEN


async def test_get_open_by_vehicle_id_returns_none_when_none_open(
    repository, vehicle_id
):
    assert await repository.get_open_by_vehicle_id(vehicle_id) is None


async def test_closed_session_is_excluded_from_open_list(
    repository, vehicle_id, operator_id
):
    session = await repository.create(
        ParkingSession(
            id=None,
            vehicle_id=vehicle_id,
            operator_id=operator_id,
            entry_time=NOW,
        )
    )
    session.status = SessionStatus.CLOSED
    await repository.update(session)

    assert await repository.get_open_by_vehicle_id(vehicle_id) is None
    assert session.id not in [s.id for s in await repository.list_open()]


async def test_update_round_trips_checkout_fields(
    repository, vehicle_id, operator_id
):
    entry_time = NOW
    session = await repository.create(
        ParkingSession(
            id=None,
            vehicle_id=vehicle_id,
            operator_id=operator_id,
            entry_time=entry_time,
        )
    )
    exit_time = NOW + timedelta(hours=1)
    session.status = SessionStatus.CLOSED
    session.exit_time = exit_time
    session.amount_charged = 6000
    session.ticket_number = f"TCK-{session.id:06d}"

    updated = await repository.update(session)

    assert updated.status == SessionStatus.CLOSED
    assert updated.exit_time == exit_time
    assert updated.amount_charged == 6000
    assert updated.ticket_number == f"TCK-{session.id:06d}"

    refetched = await repository.get_by_id(session.id)
    assert refetched.exit_time == exit_time
    assert refetched.amount_charged == 6000
    assert refetched.ticket_number == f"TCK-{session.id:06d}"


async def test_new_session_has_no_checkout_fields(
    repository, vehicle_id, operator_id
):
    session = await repository.create(
        ParkingSession(
            id=None,
            vehicle_id=vehicle_id,
            operator_id=operator_id,
            entry_time=NOW,
        )
    )

    assert session.exit_time is None
    assert session.amount_charged is None
    assert session.ticket_number is None


# --- B-UQ: one open session per vehicle, atomic close ---------------------


def _open(vehicle_id, operator_id):
    return ParkingSession(
        id=None, vehicle_id=vehicle_id, operator_id=operator_id, entry_time=NOW
    )


def _closing(session, exit_time):
    session.status = SessionStatus.CLOSED
    session.exit_time = exit_time
    session.amount_charged = 3000
    session.ticket_number = f"TCK-{session.id:06d}"
    return session


async def test_second_open_session_for_vehicle_is_rejected(
    repository, vehicle_id, operator_id
):
    await repository.create(_open(vehicle_id, operator_id))

    with pytest.raises(DuplicateOpenSessionError):
        await repository.create(_open(vehicle_id, operator_id))


async def test_new_open_session_allowed_after_previous_closed(
    repository, vehicle_id, operator_id
):
    first = await repository.create(_open(vehicle_id, operator_id))
    await repository.close(_closing(first, NOW + timedelta(hours=1)))

    second = await repository.create(_open(vehicle_id, operator_id))

    assert second.status == SessionStatus.OPEN


async def test_close_is_atomic_and_rejects_second_close(
    repository, vehicle_id, operator_id
):
    created = await repository.create(_open(vehicle_id, operator_id))
    stale_copy = await repository.get_by_id(created.id)

    closed = await repository.close(_closing(created, NOW + timedelta(hours=1)))
    second = await repository.close(_closing(stale_copy, NOW + timedelta(hours=2)))

    assert closed.status == SessionStatus.CLOSED
    assert second is None
    refetched = await repository.get_by_id(created.id)
    assert refetched.exit_time == NOW + timedelta(hours=1)


def test_model_declares_integrity_and_report_indexes():
    from app.infrastructure.models import ParkingSessionModel

    indexes = {index.name: index for index in ParkingSessionModel.__table__.indexes}

    assert indexes["uq_open_session_per_vehicle"].unique is True
    assert "ix_sessions_open_entry" in indexes
    assert "ix_sessions_status_exit" in indexes
    assert indexes["uq_sessions_ticket"].unique is True
