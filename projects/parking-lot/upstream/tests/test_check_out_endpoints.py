"""Check-out endpoint tests (Success / Failure / Security)."""

from datetime import datetime, timedelta, timezone

from app.application.check_out_service import (
    CheckOutContext,
    CheckOutRepositories,
    CheckOutService,
)
from app.application.commands import CheckOutCommand
from app.core.config import settings
from app.core.security import hash_password
from app.domain.billing import FareCalculator
from app.domain.category import Category
from app.domain.parking_session import ParkingSession
from app.domain.tariff import Tariff, TariffType
from app.domain.user import User, UserRole
from app.domain.vehicle import Vehicle
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.monthly_pass_repository import (
    SqlAlchemyMonthlyPassRepository,
)
from app.infrastructure.repositories.parking_session_repository import (
    SqlAlchemyParkingSessionRepository,
)
from app.infrastructure.repositories.tariff_repository import (
    SqlAlchemyTariffRepository,
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


async def _create_vehicle_with_hourly_tariff(
    client, headers, plate="ABC123", amount=3000
):
    category = await client.post(
        "/api/categories", json={"name": f"carro-{plate}"}, headers=headers
    )
    category_id = category.json()["id"]
    await client.post(
        "/api/tariffs",
        json={"category_id": category_id, "type": "hourly", "amount": amount},
        headers=headers,
    )
    vehicle = await client.post(
        "/api/vehicles",
        json={"plate": plate, "category_id": category_id},
        headers=headers,
    )
    return vehicle.json()


async def _check_in(client, headers, plate):
    response = await client.post(
        "/api/check-ins", data={"plate": plate}, headers=headers
    )
    return response.json()


async def test_check_out_open_session_charges_fare(client, session_factory, clock):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle_with_hourly_tariff(client, admin_headers, plate="OUT001")
    operator_headers = await _operator_headers(client, session_factory)
    check_in = await _check_in(client, operator_headers, "OUT001")
    session_id = check_in["id"]
    clock.advance(timedelta(minutes=50))

    response = await client.post(
        f"/api/check-outs/{session_id}", headers=operator_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["amount_charged"] == 3000  # 50 min ceil -> 1h * 3000
    assert body["ticket_number"] == f"TCK-{session_id:06d}"
    assert body["plate"] == "OUT001"
    assert datetime.fromisoformat(body["exit_time"]) == clock.now


async def test_check_out_service_computes_exact_amount_for_injected_exit_time(
    session_factory, clock
):
    """Service-level determinism check: fixed entry/exit -> exact fare."""
    async with session_factory() as session:
        category_repository = SqlAlchemyCategoryRepository(session)
        category = await category_repository.create(Category(id=None, name="carro"))
        tariff_repository = SqlAlchemyTariffRepository(session)
        await tariff_repository.create(
            Tariff(
                id=None,
                category_id=category.id,
                type=TariffType.HOURLY,
                amount=3000,
                start_time=None,
                end_time=None,
            )
        )
        vehicle_repository = SqlAlchemyVehicleRepository(session)
        vehicle = await vehicle_repository.create(
            Vehicle(id=None, plate="EXACT01", category_id=category.id)
        )
        user_repository = SqlAlchemyUserRepository(session)
        operator = await user_repository.create(
            User(
                id=None,
                username="op-exact",
                display_name="Operator",
                role=UserRole.OPERATOR,
                pin_hash="hash",
            )
        )
        session_repository = SqlAlchemyParkingSessionRepository(session)
        entry_time = clock.now - timedelta(hours=3)
        parking_session = await session_repository.create(
            ParkingSession(
                id=None,
                vehicle_id=vehicle.id,
                operator_id=operator.id,
                entry_time=entry_time,
            )
        )
        await session.commit()

        monthly_pass_repository = SqlAlchemyMonthlyPassRepository(session)
        service = CheckOutService(
            CheckOutRepositories(
                session_repository,
                vehicle_repository,
                tariff_repository,
                monthly_pass_repository,
            ),
            CheckOutContext(FareCalculator(settings.business_zone), clock),
        )
        exit_time = entry_time + timedelta(hours=1, minutes=5)

        result = await service.close_session(CheckOutCommand(parking_session.id, exit_time))
        closed = result.session

        assert closed.amount_charged == 6000  # 2h ceil * 3000
        assert closed.exit_time == exit_time
        assert closed.ticket_number == f"TCK-{parking_session.id:06d}"


async def test_check_out_uses_client_supplied_exit_time(
    client, session_factory, clock
):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle_with_hourly_tariff(client, admin_headers, plate="OUT005")
    operator_headers = await _operator_headers(client, session_factory)
    check_in = await _check_in(client, operator_headers, "OUT005")
    session_id = check_in["id"]
    entry_time = datetime.fromisoformat(check_in["entry_time"])
    client_exit_time = entry_time + timedelta(hours=2)
    clock.advance(timedelta(hours=3))  # queued offline, synced later

    response = await client.post(
        f"/api/check-outs/{session_id}",
        json={"client_exit_time": client_exit_time.isoformat()},
        headers=operator_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["exit_time"]) == client_exit_time
    assert body["amount_charged"] == 6000  # 2h ceil * 3000


async def test_check_out_unknown_session_is_not_found(client, session_factory):
    operator_headers = await _operator_headers(client, session_factory)

    response = await client.post("/api/check-outs/999999", headers=operator_headers)

    assert response.status_code == 404


async def test_check_out_already_closed_session_is_conflict(
    client, session_factory, clock
):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle_with_hourly_tariff(client, admin_headers, plate="OUT002")
    operator_headers = await _operator_headers(client, session_factory)
    check_in = await _check_in(client, operator_headers, "OUT002")
    session_id = check_in["id"]
    clock.advance(timedelta(minutes=30))
    await client.post(f"/api/check-outs/{session_id}", headers=operator_headers)

    response = await client.post(
        f"/api/check-outs/{session_id}", headers=operator_headers
    )

    assert response.status_code == 409


async def test_unauthenticated_check_out_is_rejected(client, session_factory):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle_with_hourly_tariff(client, admin_headers, plate="OUT003")
    operator_headers = await _operator_headers(client, session_factory)
    check_in = await _check_in(client, operator_headers, "OUT003")
    session_id = check_in["id"]

    response = await client.post(f"/api/check-outs/{session_id}")

    assert response.status_code == 401


async def test_check_out_with_active_monthly_pass_charges_zero(
    client, session_factory, clock
):
    admin_headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle_with_hourly_tariff(
        client, admin_headers, plate="OUT004"
    )
    today = clock.now.date()
    await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle["id"],
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "amount": 100000,
        },
        headers=admin_headers,
    )
    operator_headers = await _operator_headers(client, session_factory)
    check_in = await _check_in(client, operator_headers, "OUT004")
    session_id = check_in["id"]
    clock.advance(timedelta(hours=2))

    response = await client.post(
        f"/api/check-outs/{session_id}", headers=operator_headers
    )

    assert response.status_code == 200
    assert response.json()["amount_charged"] == 0


# --- B-EXIT: client_exit_time bounds ---------------------------------------


async def _open_session(client, session_factory, plate):
    admin_headers = await _admin_headers(client, session_factory)
    await _create_vehicle_with_hourly_tariff(client, admin_headers, plate=plate)
    operator_headers = await _operator_headers(client, session_factory)
    check_in = await _check_in(client, operator_headers, plate)
    entry_time = datetime.fromisoformat(check_in["entry_time"])
    return check_in["id"], entry_time, operator_headers


async def _check_out_at(client, session_id, headers, exit_time_iso):
    return await client.post(
        f"/api/check-outs/{session_id}",
        json={"client_exit_time": exit_time_iso},
        headers=headers,
    )


async def test_check_out_accepts_exit_within_clock_skew(client, session_factory, clock):
    session_id, _, headers = await _open_session(client, session_factory, "SKEW01")
    clock.advance(timedelta(hours=1))
    exit_time = clock.now + timedelta(minutes=4)

    response = await _check_out_at(client, session_id, headers, exit_time.isoformat())

    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["exit_time"]) == exit_time


async def test_check_out_rejects_exit_before_entry(client, session_factory, clock):
    session_id, entry_time, headers = await _open_session(
        client, session_factory, "SKEW02"
    )
    clock.advance(timedelta(hours=1))
    exit_time = entry_time - timedelta(minutes=1)

    response = await _check_out_at(client, session_id, headers, exit_time.isoformat())

    assert response.status_code == 422
    assert "client_exit_time" in response.json()["detail"]
    session = await client.get("/api/check-ins", headers=headers)
    assert [s["id"] for s in session.json()] == [session_id]  # still open


async def test_check_out_rejects_exit_equal_to_entry(client, session_factory, clock):
    session_id, entry_time, headers = await _open_session(
        client, session_factory, "SKEW03"
    )

    response = await _check_out_at(
        client, session_id, headers, entry_time.isoformat()
    )

    assert response.status_code == 422


async def test_check_out_rejects_naive_exit_time(client, session_factory, clock):
    session_id, _, headers = await _open_session(client, session_factory, "SKEW04")
    clock.advance(timedelta(hours=1))
    naive = clock.now.replace(tzinfo=None).isoformat()

    response = await _check_out_at(client, session_id, headers, naive)

    assert response.status_code == 422


async def test_check_out_rejects_exit_beyond_future_skew(
    client, session_factory, clock
):
    """Security: a client cannot inflate/deflate fares with a far-future exit."""
    session_id, _, headers = await _open_session(client, session_factory, "SKEW05")
    clock.advance(timedelta(hours=1))
    exit_time = clock.now + timedelta(minutes=6)

    response = await _check_out_at(client, session_id, headers, exit_time.isoformat())

    assert response.status_code == 422
    assert "5 minutes" in response.json()["detail"]


async def test_check_out_normalizes_offset_exit_time_to_utc(
    client, session_factory, clock
):
    session_id, entry_time, headers = await _open_session(
        client, session_factory, "SKEW06"
    )
    clock.advance(timedelta(hours=3))
    local_exit = (entry_time + timedelta(hours=2)).astimezone(
        timezone(timedelta(hours=-5))
    )

    response = await _check_out_at(client, session_id, headers, local_exit.isoformat())

    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["exit_time"]) == local_exit
    assert body["amount_charged"] == 6000
