"""Vehicle endpoint tests (Success / Failure / Security)."""

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


async def test_admin_can_create_and_search_vehicle(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)

    created = await client.post(
        "/api/vehicles",
        json={"plate": "abc 123", "category_id": category_id, "color": "red"},
        headers=headers,
    )
    searched = await client.get("/api/vehicles?plate=ABC123", headers=headers)

    assert created.status_code == 201
    assert created.json()["plate"] == "ABC123"
    assert searched.json()[0]["color"] == "red"


async def test_duplicate_plate_is_rejected(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)
    await client.post(
        "/api/vehicles",
        json={"plate": "ABC123", "category_id": category_id},
        headers=headers,
    )

    response = await client.post(
        "/api/vehicles",
        json={"plate": "abc123", "category_id": category_id},
        headers=headers,
    )

    assert response.status_code == 409


async def test_operator_cannot_create_vehicle(client, session_factory):
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
        "/api/vehicles",
        json={"plate": "ABC123", "category_id": category_id},
        headers={"Authorization": f"Bearer {op_token}"},
    )

    assert response.status_code == 403


async def test_admin_can_update_and_delete_vehicle(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    category_id = await _create_category(client, headers)
    created = await client.post(
        "/api/vehicles",
        json={"plate": "ABC123", "category_id": category_id},
        headers=headers,
    )
    vehicle_id = created.json()["id"]

    updated = await client.patch(
        f"/api/vehicles/{vehicle_id}",
        json={"color": "blue", "brand": "Toyota"},
        headers=headers,
    )
    deleted = await client.delete(f"/api/vehicles/{vehicle_id}", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["color"] == "blue"
    assert deleted.status_code == 204
