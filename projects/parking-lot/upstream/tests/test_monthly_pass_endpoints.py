"""Monthly pass endpoint tests (Success / Failure / Security)."""

from datetime import date, timedelta

from app.core.security import hash_password
from app.domain.user import User, UserRole
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository


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


async def _admin_headers(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN)
    token = (await _login(client, "admin")).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_vehicle(client, headers, plate="ABC123"):
    category = await client.post(
        "/api/categories", json={"name": f"carro-{plate}"}, headers=headers
    )
    category_id = category.json()["id"]
    vehicle = await client.post(
        "/api/vehicles",
        json={"plate": plate, "category_id": category_id},
        headers=headers,
    )
    return vehicle.json()


def _dates():
    today = date(2026, 3, 10)
    return (today - timedelta(days=1)).isoformat(), (today + timedelta(days=30)).isoformat()


async def test_admin_can_create_monthly_pass_for_existing_vehicle(
    client, session_factory
):
    headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle(client, headers)
    start_date, end_date = _dates()

    response = await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle["id"],
            "start_date": start_date,
            "end_date": end_date,
            "amount": 100000,
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["vehicle_id"] == vehicle["id"]
    assert body["active"] is True


async def test_create_monthly_pass_for_unknown_vehicle_is_not_found(
    client, session_factory
):
    headers = await _admin_headers(client, session_factory)
    start_date, end_date = _dates()

    response = await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": 999999,
            "start_date": start_date,
            "end_date": end_date,
            "amount": 100000,
        },
        headers=headers,
    )

    assert response.status_code == 404


async def test_create_monthly_pass_with_invalid_date_range_is_rejected(
    client, session_factory
):
    headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle(client, headers)
    today = date(2026, 3, 10).isoformat()

    response = await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle["id"],
            "start_date": today,
            "end_date": today,
            "amount": 100000,
        },
        headers=headers,
    )

    assert response.status_code == 422


async def test_operator_cannot_create_monthly_pass(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle(client, headers)
    start_date, end_date = _dates()
    await client.post(
        "/api/users",
        json={
            "username": "op",
            "display_name": "Operator",
            "role": "operator",
            "pin": "5678",
        },
        headers=headers,
    )
    op_token = (await _login(client, "op", "5678")).json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    response = await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle["id"],
            "start_date": start_date,
            "end_date": end_date,
            "amount": 100000,
        },
        headers=op_headers,
    )

    assert response.status_code == 403


async def test_operator_cannot_update_or_delete_monthly_pass(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle(client, headers)
    start_date, end_date = _dates()
    created = await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle["id"],
            "start_date": start_date,
            "end_date": end_date,
            "amount": 100000,
        },
        headers=headers,
    )
    pass_id = created.json()["id"]
    await client.post(
        "/api/users",
        json={
            "username": "op2",
            "display_name": "Operator2",
            "role": "operator",
            "pin": "5678",
        },
        headers=headers,
    )
    op_token = (await _login(client, "op2", "5678")).json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    updated = await client.patch(
        f"/api/monthly-passes/{pass_id}",
        json={"active": False},
        headers=op_headers,
    )
    deleted = await client.delete(
        f"/api/monthly-passes/{pass_id}", headers=op_headers
    )

    assert updated.status_code == 403
    assert deleted.status_code == 403


async def test_admin_can_update_and_delete_monthly_pass(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    vehicle = await _create_vehicle(client, headers)
    start_date, end_date = _dates()
    created = await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle["id"],
            "start_date": start_date,
            "end_date": end_date,
            "amount": 100000,
        },
        headers=headers,
    )
    pass_id = created.json()["id"]

    updated = await client.patch(
        f"/api/monthly-passes/{pass_id}",
        json={"active": False},
        headers=headers,
    )
    deleted = await client.delete(f"/api/monthly-passes/{pass_id}", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert deleted.status_code == 204


async def test_list_monthly_passes_filtered_by_vehicle(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    vehicle_a = await _create_vehicle(client, headers, plate="AAA111")
    vehicle_b = await _create_vehicle(client, headers, plate="BBB222")
    start_date, end_date = _dates()
    await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle_a["id"],
            "start_date": start_date,
            "end_date": end_date,
            "amount": 100000,
        },
        headers=headers,
    )
    await client.post(
        "/api/monthly-passes",
        json={
            "vehicle_id": vehicle_b["id"],
            "start_date": start_date,
            "end_date": end_date,
            "amount": 50000,
        },
        headers=headers,
    )

    response = await client.get(
        f"/api/monthly-passes?vehicle_id={vehicle_a['id']}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["vehicle_id"] == vehicle_a["id"]
