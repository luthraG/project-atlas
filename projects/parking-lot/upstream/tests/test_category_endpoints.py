"""Category endpoint tests (Success / Failure / Security)."""

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


async def test_admin_can_create_and_list_category(client, session_factory):
    headers = await _admin_headers(client, session_factory)

    created = await client.post(
        "/api/categories", json={"name": "carro"}, headers=headers
    )
    listed = await client.get("/api/categories", headers=headers)

    assert created.status_code == 201
    assert created.json()["name"] == "carro"
    assert any(item["name"] == "carro" for item in listed.json())


async def test_duplicate_category_name_is_rejected(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    await client.post("/api/categories", json={"name": "moto"}, headers=headers)

    response = await client.post(
        "/api/categories", json={"name": "moto"}, headers=headers
    )

    assert response.status_code == 409


async def test_operator_cannot_create_category(client, session_factory):
    headers = await _admin_headers(client, session_factory)
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
        "/api/categories",
        json={"name": "bus"},
        headers={"Authorization": f"Bearer {op_token}"},
    )

    assert response.status_code == 403


async def test_list_requires_authentication(client):
    response = await client.get("/api/categories")

    assert response.status_code in (401, 403)


async def test_admin_can_update_and_delete_category(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    created = await client.post(
        "/api/categories", json={"name": "camioneta"}, headers=headers
    )
    category_id = created.json()["id"]

    updated = await client.patch(
        f"/api/categories/{category_id}",
        json={"name": "camion"},
        headers=headers,
    )
    deleted = await client.delete(f"/api/categories/{category_id}", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["name"] == "camion"
    assert deleted.status_code == 204
