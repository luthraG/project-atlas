"""Tariff endpoint tests (Success / Failure / Security)."""

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


async def _create_category(client, headers, name="carro"):
    response = await client.post(
        "/api/categories", json={"name": name}, headers=headers
    )
    return response.json()["id"]


async def test_admin_can_create_and_list_tariff(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)

    created = await client.post(
        "/api/tariffs",
        json={"category_id": category_id, "type": "hourly", "amount": 3000},
        headers=headers,
    )
    listed = await client.get("/api/tariffs", headers=headers)

    assert created.status_code == 201
    assert created.json()["amount"] == 3000
    assert any(item["type"] == "hourly" for item in listed.json())


async def test_non_positive_amount_is_rejected(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)

    response = await client.post(
        "/api/tariffs",
        json={"category_id": category_id, "type": "hourly", "amount": 0},
        headers=headers,
    )

    assert response.status_code == 422


async def test_nightly_without_window_is_rejected(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)

    response = await client.post(
        "/api/tariffs",
        json={"category_id": category_id, "type": "nightly", "amount": 5000},
        headers=headers,
    )

    assert response.status_code == 422


async def test_operator_cannot_create_tariff(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)
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

    response = await client.post(
        "/api/tariffs",
        json={"category_id": category_id, "type": "hourly", "amount": 3000},
        headers={"Authorization": f"Bearer {op_token}"},
    )

    assert response.status_code == 403


async def test_admin_can_deactivate_and_delete_tariff(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)
    created = await client.post(
        "/api/tariffs",
        json={"category_id": category_id, "type": "daily", "amount": 20000},
        headers=headers,
    )
    tariff_id = created.json()["id"]

    updated = await client.patch(
        f"/api/tariffs/{tariff_id}", json={"active": False}, headers=headers
    )
    deleted = await client.delete(f"/api/tariffs/{tariff_id}", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert deleted.status_code == 204


async def test_overlong_tariff_time_is_rejected(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category = await client.post(
        "/api/categories", json={"name": "len-check"}, headers=headers
    )

    response = await client.post(
        "/api/tariffs",
        json={"category_id": category.json()["id"], "type": "nightly",
              "amount": 1000, "start_time": "22:00:00", "end_time": "06:00"},
        headers=headers,
    )

    assert response.status_code == 422
