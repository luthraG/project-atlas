"""Behaviour SQLite cannot prove: run with TEST_DATABASE_URL + `-m postgres`.

Skipped automatically when TEST_DATABASE_URL is unset.
"""

import os
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.domain.category import Category
from app.domain.errors import DomainValidationError, DuplicateOpenSessionError
from app.domain.parking_session import ParkingSession
from app.domain.user import User, UserRole
from app.domain.vehicle import Vehicle
from app.infrastructure.database import Base, session_scope
from app.infrastructure.models import VehicleModel
from app.infrastructure.repositories.category_repository import SqlAlchemyCategoryRepository
from app.infrastructure.repositories.parking_session_repository import (
    SqlAlchemyParkingSessionRepository,
)
from app.infrastructure.repositories.report_repository import SqlAlchemyReportRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.repositories.vehicle_repository import SqlAlchemyVehicleRepository

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture
async def pg_factory():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _vehicle_and_operator(session) -> tuple[int, int]:
    category = await SqlAlchemyCategoryRepository(session).create(Category(None, "carro"))
    vehicle = await SqlAlchemyVehicleRepository(session).create(
        Vehicle(None, "PG001", category.id)
    )
    operator = await SqlAlchemyUserRepository(session).create(
        User(None, "op", "Op", UserRole.OPERATOR, "hash")
    )
    return vehicle.id, operator.id


async def test_partial_unique_index_allows_one_open_session(pg_factory):
    async with pg_factory() as session:
        vehicle_id, operator_id = await _vehicle_and_operator(session)
        sessions = SqlAlchemyParkingSessionRepository(session)
        entry = datetime(2026, 3, 10, 14, tzinfo=UTC)
        await sessions.create(ParkingSession(None, vehicle_id, operator_id, entry))

        with pytest.raises(DuplicateOpenSessionError):
            await sessions.create(ParkingSession(None, vehicle_id, operator_id, entry))


async def test_varchar_overflow_becomes_domain_validation_error(pg_factory):
    with pytest.raises(DomainValidationError):
        async with session_scope(pg_factory) as session:
            session.add(VehicleModel(plate="X" * 25, category_id=1))
            await session.flush()


async def test_oversized_fields_over_http_are_422_not_500(pg_factory, client_for):
    async with pg_factory() as session:
        await SqlAlchemyUserRepository(session).create(
            User(None, "admin", "Admin", UserRole.ADMIN, hash_password("1234"))
        )
        await session.commit()

    async with client_for(pg_factory, raise_app_exceptions=False) as client:
        login = await client.post("/api/auth/login", json={"username": "admin", "pin": "1234"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        category = await client.post("/api/categories", json={"name": "c" * 51}, headers=headers)
        vehicle = await client.post(
            "/api/vehicles", json={"plate": "P" * 21, "category_id": 1}, headers=headers
        )

    assert category.status_code == 422
    assert vehicle.status_code == 422


async def test_revenue_groups_by_business_local_day(pg_factory):
    async with pg_factory() as session:
        vehicle_id, operator_id = await _vehicle_and_operator(session)
        sessions = SqlAlchemyParkingSessionRepository(session)
        # 03:00 UTC on the 10th == 22:00 on the 9th in America/Bogota.
        exit_time = datetime(2026, 3, 10, 3, tzinfo=UTC)
        opened = await sessions.create(ParkingSession(
            None, vehicle_id, operator_id, datetime(2026, 3, 10, 1, tzinfo=UTC)))
        opened.exit_time, opened.amount_charged = exit_time, 3000
        opened.ticket_number = "TCK-PG"
        await sessions.close(opened)
        await session.commit()

        report = await SqlAlchemyReportRepository(session, "America/Bogota").revenue_by_range(
            date(2026, 3, 9), date(2026, 3, 9)
        )

    assert report.total == 3000
    assert [(d.date, d.amount) for d in report.by_day] == [("2026-03-09", 3000)]
