"""Monthly pass repository tests (Success / Failure / Security)."""

from datetime import date, timedelta

import pytest

from app.domain.category import Category
from app.domain.monthly_pass import MonthlyPass
from app.domain.vehicle import Vehicle
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.monthly_pass_repository import (
    SqlAlchemyMonthlyPassRepository,
)
from app.infrastructure.repositories.vehicle_repository import (
    SqlAlchemyVehicleRepository,
)


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
async def repository(session_factory):
    async with session_factory() as session:
        yield SqlAlchemyMonthlyPassRepository(session)


async def test_create_and_get_monthly_pass(repository, vehicle_id):
    today = date(2026, 1, 15)
    created = await repository.create(
        MonthlyPass(
            id=None,
            vehicle_id=vehicle_id,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            amount=100000,
        )
    )

    fetched = await repository.get_by_id(created.id)

    assert fetched is not None
    assert fetched.vehicle_id == vehicle_id
    assert fetched.amount == 100000
    assert fetched.active is True


async def test_get_active_for_vehicle_matches_in_range_pass(repository, vehicle_id):
    today = date(2026, 1, 15)
    await repository.create(
        MonthlyPass(
            id=None,
            vehicle_id=vehicle_id,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            amount=100000,
        )
    )

    active = await repository.get_active_for_vehicle(vehicle_id, today)

    assert active is not None
    assert active.vehicle_id == vehicle_id


async def test_get_active_for_vehicle_returns_none_for_out_of_range_date(
    repository, vehicle_id
):
    today = date(2026, 1, 15)
    await repository.create(
        MonthlyPass(
            id=None,
            vehicle_id=vehicle_id,
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=1),
            amount=100000,
        )
    )

    active = await repository.get_active_for_vehicle(vehicle_id, today)

    assert active is None


async def test_get_by_id_returns_none_for_unknown_id(repository):
    assert await repository.get_by_id(999999) is None
