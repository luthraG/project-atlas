"""Report endpoint tests (Success / Failure / Security)."""

from datetime import UTC, datetime

from app.core.security import hash_password
from app.domain.category import Category
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


async def _seed_user(session_factory, username, role, pin="1234"):
    async with session_factory() as session:
        repository = SqlAlchemyUserRepository(session)
        await repository.create(
            User(
                id=None,
                username=username,
                display_name=username.title(),
                role=role,
                pin_hash=hash_password(pin),
            )
        )
        await session.commit()


async def _login(client, username, pin="1234"):
    return await client.post(
        "/api/auth/login", json={"username": username, "pin": pin}
    )


async def _operator_headers(client, session_factory):
    await _seed_user(session_factory, "operator", UserRole.OPERATOR)
    token = (await _login(client, "operator")).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _admin_headers(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN)
    token = (await _login(client, "admin")).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_sessions(session_factory):
    """2 categories, 2 vehicles, mixed closed/open sessions.

    - moto: closed inside range (2026-02-02, amount 2000), 1 open session.
    - carro: closed outside range (2026-02-20, amount 8000, excluded).
    """
    async with session_factory() as session:
        categories = SqlAlchemyCategoryRepository(session)
        moto = await categories.create(Category(id=None, name="moto"))
        carro = await categories.create(Category(id=None, name="carro"))

        vehicles = SqlAlchemyVehicleRepository(session)
        moto_vehicle = await vehicles.create(
            Vehicle(id=None, plate="REP-M1", category_id=moto.id)
        )
        carro_vehicle = await vehicles.create(
            Vehicle(id=None, plate="REP-C1", category_id=carro.id)
        )

        users = SqlAlchemyUserRepository(session)
        operator = await users.create(
            User(
                id=None,
                username="operator-seed",
                display_name="Operator",
                role=UserRole.OPERATOR,
                pin_hash="hash",
            )
        )

        sessions = SqlAlchemyParkingSessionRepository(session)

        closed_in_range = await sessions.create(
            ParkingSession(
                id=None,
                vehicle_id=moto_vehicle.id,
                operator_id=operator.id,
                entry_time=datetime(2026, 2, 2, 8, 0, tzinfo=UTC),
            )
        )
        closed_in_range.status = SessionStatus.CLOSED
        closed_in_range.exit_time = datetime(2026, 2, 2, 10, 0, tzinfo=UTC)
        closed_in_range.amount_charged = 2000
        closed_in_range.ticket_number = "TCK-000001"
        await sessions.update(closed_in_range)

        closed_out_of_range = await sessions.create(
            ParkingSession(
                id=None,
                vehicle_id=carro_vehicle.id,
                operator_id=operator.id,
                entry_time=datetime(2026, 2, 20, 8, 0, tzinfo=UTC),
            )
        )
        closed_out_of_range.status = SessionStatus.CLOSED
        closed_out_of_range.exit_time = datetime(2026, 2, 20, 9, 0, tzinfo=UTC)
        closed_out_of_range.amount_charged = 8000
        closed_out_of_range.ticket_number = "TCK-000002"
        await sessions.update(closed_out_of_range)

        await sessions.create(
            ParkingSession(
                id=None,
                vehicle_id=moto_vehicle.id,
                operator_id=operator.id,
                entry_time=datetime(2026, 2, 3, 8, 0, tzinfo=UTC),
            )
        )

        await session.commit()


async def test_revenue_report_sums_by_day_and_category_within_range(
    client, session_factory
):
    await _seed_sessions(session_factory)
    admin_headers = await _admin_headers(client, session_factory)

    response = await client.get(
        "/api/reports/revenue",
        params={"start_date": "2026-02-01", "end_date": "2026-02-05"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2000
    assert body["by_day"] == [{"date": "2026-02-02", "amount": 2000}]
    assert body["by_category"] == [
        {
            "category_id": body["by_category"][0]["category_id"],
            "category_name": "moto",
            "amount": 2000,
        }
    ]
    amounts = [entry["amount"] for entry in body["by_day"]]
    assert 8000 not in amounts
    category_names = [entry["category_name"] for entry in body["by_category"]]
    assert "carro" not in category_names


async def test_occupancy_report_counts_only_open_sessions_by_category(
    client, session_factory
):
    await _seed_sessions(session_factory)
    admin_headers = await _admin_headers(client, session_factory)

    response = await client.get("/api/reports/occupancy", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total_open"] == 1
    assert body["by_category"] == [
        {
            "category_id": body["by_category"][0]["category_id"],
            "category_name": "moto",
            "count": 1,
        }
    ]


async def test_revenue_report_rejects_start_after_end_date(client, session_factory):
    admin_headers = await _admin_headers(client, session_factory)

    response = await client.get(
        "/api/reports/revenue",
        params={"start_date": "2026-02-10", "end_date": "2026-02-01"},
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_operator_cannot_fetch_revenue_report(client, session_factory):
    operator_headers = await _operator_headers(client, session_factory)

    response = await client.get(
        "/api/reports/revenue",
        params={"start_date": "2026-02-01", "end_date": "2026-02-05"},
        headers=operator_headers,
    )

    assert response.status_code == 403


async def test_operator_cannot_fetch_occupancy_report(client, session_factory):
    operator_headers = await _operator_headers(client, session_factory)

    response = await client.get("/api/reports/occupancy", headers=operator_headers)

    assert response.status_code == 403
