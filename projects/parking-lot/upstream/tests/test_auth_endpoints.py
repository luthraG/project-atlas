"""Auth and user management endpoint tests (Success / Failure / Security)."""

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


async def _login(client, username, pin):
    return await client.post(
        "/api/auth/login", json={"username": username, "pin": pin}
    )


async def _admin_headers(client, session_factory, username="admin", pin="1234"):
    await _seed_user(session_factory, username, UserRole.ADMIN, pin)
    token = (await _login(client, username, pin)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_create_user_and_login(client, session_factory):
    headers = await _admin_headers(client, session_factory)

    create = await client.post(
        "/api/users",
        json={
            "username": "op",
            "display_name": "Operator",
            "role": "operator",
            "pin": "5678",
        },
        headers=headers,
    )
    assert create.status_code == 201
    assert create.json()["role"] == "operator"

    login = await _login(client, "op", "5678")
    assert login.status_code == 200


async def test_login_with_wrong_pin_is_rejected(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN, "1234")

    login = await _login(client, "admin", "0000")

    assert login.status_code == 401


async def test_deactivated_user_cannot_login(client, session_factory):
    headers = await _admin_headers(client, session_factory)
    created = await client.post(
        "/api/users",
        json={
            "username": "op",
            "display_name": "Operator",
            "role": "operator",
            "pin": "5678",
        },
        headers=headers,
    )
    op_id = created.json()["id"]

    await client.patch(
        f"/api/users/{op_id}", json={"is_active": False}, headers=headers
    )

    login = await _login(client, "op", "5678")
    assert login.status_code == 401


async def test_operator_cannot_manage_users(client, session_factory):
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

    response = await client.get(
        "/api/users", headers={"Authorization": f"Bearer {op_token}"}
    )

    assert response.status_code == 403


async def test_duplicate_username_is_rejected(client, session_factory):
    headers = await _admin_headers(client, session_factory)

    response = await client.post(
        "/api/users",
        json={
            "username": "admin",
            "display_name": "Other",
            "role": "operator",
            "pin": "9999",
        },
        headers=headers,
    )

    assert response.status_code == 409


async def test_requires_auth_for_user_list(client):
    response = await client.get("/api/users")

    assert response.status_code in (401, 403)


# --- B-RL: login rate limiting / lockout ----------------------------------

GENERIC_429 = "Too many attempts, try later"
BODY_429 = {"detail": GENERIC_429, "code": "TooManyLoginAttemptsError"}


async def _fail_times(client, username, times):
    for _ in range(times):
        response = await _login(client, username, "0000")
        assert response.status_code == 401


async def test_login_success_resets_failure_count(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN, "1234")
    await _fail_times(client, "admin", 4)

    assert (await _login(client, "admin", "1234")).status_code == 200
    await _fail_times(client, "admin", 4)
    assert (await _login(client, "admin", "1234")).status_code == 200


async def test_five_failures_lock_out_even_the_correct_pin(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN, "1234")
    await _fail_times(client, "admin", 5)

    response = await _login(client, "admin", "1234")

    assert response.status_code == 429
    assert response.json() == BODY_429
    assert response.headers.get("retry-after") is not None


async def test_lockout_expires_after_window(client, session_factory, clock):
    from datetime import timedelta

    await _seed_user(session_factory, "admin", UserRole.ADMIN, "1234")
    await _fail_times(client, "admin", 5)
    clock.advance(timedelta(minutes=15, seconds=1))

    assert (await _login(client, "admin", "1234")).status_code == 200


async def test_lockout_response_does_not_reveal_user_existence(
    client, session_factory
):
    await _seed_user(session_factory, "admin", UserRole.ADMIN, "1234")
    await _fail_times(client, "admin", 5)
    await _fail_times(client, "ghost", 5)

    existing = await _login(client, "admin", "0000")
    missing = await _login(client, "ghost", "0000")

    assert existing.status_code == missing.status_code == 429
    assert existing.json() == missing.json() == BODY_429


async def test_lockout_is_scoped_to_username(client, session_factory):
    await _seed_user(session_factory, "admin", UserRole.ADMIN, "1234")
    await _seed_user(session_factory, "other", UserRole.OPERATOR, "5678")
    await _fail_times(client, "admin", 5)

    assert (await _login(client, "other", "5678")).status_code == 200


async def test_unknown_user_still_runs_password_verification(
    client, session_factory, monkeypatch
):
    """Security: equalize timing so usernames cannot be enumerated."""
    from app.core import security

    calls = []
    original = security.verify_password_async

    async def spy(pin, hashed):
        calls.append(hashed)
        return await original(pin, hashed)

    monkeypatch.setattr(security, "verify_password_async", spy)

    response = await _login(client, "ghost", "1234")

    assert response.status_code == 401
    assert calls == [None]


async def test_oversized_login_fields_are_rejected(client):
    response = await client.post(
        "/api/auth/login", json={"username": "a" * 51, "pin": "1234"}
    )

    assert response.status_code == 422
