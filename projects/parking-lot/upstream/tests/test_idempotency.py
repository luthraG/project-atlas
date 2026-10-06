"""Idempotency-Key on offline-outbox writes (check-in create, check-out close)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.domain.user import UserRole
from app.infrastructure.models import IdempotencyKeyModel, ParkingSessionModel


async def _login_headers(client, seed_user, username):
    await seed_user(username, UserRole.OPERATOR)
    response = await client.post("/api/auth/login", json={"username": username, "pin": "1234"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def category_id(client, admin_headers):
    category = await client.post("/api/categories", json={"name": "carro"}, headers=admin_headers)
    await client.post(
        "/api/tariffs",
        json={"category_id": category.json()["id"], "type": "hourly", "amount": 3000},
        headers=admin_headers,
    )
    return category.json()["id"]


async def _check_in(client, headers, category_id, key, plate="IDEM1"):
    return await client.post(
        "/api/check-ins",
        data={"plate": plate, "category_id": category_id},
        headers={**headers, "Idempotency-Key": key},
    )


async def _session_count(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count(ParkingSessionModel.id)))


async def test_replayed_check_in_returns_same_session(
    client, session_factory, operator_headers, category_id
):
    first = await _check_in(client, operator_headers, category_id, "key-1")

    replay = await _check_in(client, operator_headers, category_id, "key-1")

    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.json()["plate"] == "IDEM1"
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert await _session_count(session_factory) == 1


async def test_without_key_second_check_in_conflicts(client, operator_headers, category_id):
    await client.post("/api/check-ins", data={"plate": "IDEM1", "category_id": category_id},
                      headers=operator_headers)

    response = await client.post(
        "/api/check-ins", data={"plate": "IDEM1", "category_id": category_id},
        headers=operator_headers,
    )

    assert response.status_code == 409


async def test_failed_request_is_not_stored(client, operator_headers, category_id):
    missing = await client.post(
        "/api/check-ins", data={"plate": "NOCAT"},
        headers={**operator_headers, "Idempotency-Key": "key-f"},
    )

    retry = await _check_in(client, operator_headers, category_id, "key-f", plate="NOCAT")

    assert missing.status_code == 422
    assert retry.status_code == 201


async def test_replayed_check_out_returns_stored_ticket(
    client, clock, operator_headers, category_id
):
    session_id = (await _check_in(client, operator_headers, category_id, "in-1")).json()["id"]
    clock.advance(timedelta(minutes=30))
    headers = {**operator_headers, "Idempotency-Key": "out-1"}

    first = await client.post(f"/api/check-outs/{session_id}", headers=headers)
    replay = await client.post(f"/api/check-outs/{session_id}", headers=headers)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()


async def test_same_key_on_other_endpoint_is_422(client, clock, operator_headers, category_id):
    await _check_in(client, operator_headers, category_id, "shared")
    session_id = (await _check_in(client, operator_headers, category_id, "k2", "B2")).json()["id"]

    response = await client.post(
        f"/api/check-outs/{session_id}", headers={**operator_headers, "Idempotency-Key": "shared"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IdempotencyKeyMismatchError"


async def test_key_reused_by_other_user_does_not_leak(
    client, seed_user, operator_headers, category_id
):
    await _check_in(client, operator_headers, category_id, "stolen")
    intruder = await _login_headers(client, seed_user, "intruder")

    response = await _check_in(client, intruder, category_id, "stolen", plate="OTHER")

    assert response.status_code == 409
    assert response.json() == {"detail": "Idempotency-Key already used",
                               "code": "IdempotencyKeyInUseError"}


async def test_oversized_key_is_rejected(client, operator_headers, category_id):
    response = await _check_in(client, operator_headers, category_id, "k" * 101)

    assert response.status_code == 422


async def test_records_older_than_48h_are_purged_on_write(
    client, clock, session_factory, operator_headers, category_id
):
    await _check_in(client, operator_headers, category_id, "old")
    clock.advance(timedelta(hours=49))

    await _check_in(client, operator_headers, category_id, "new", plate="FRESH")

    async with session_factory() as session:
        keys = set(await session.scalars(select(IdempotencyKeyModel.key)))
    assert keys == {"new"}
