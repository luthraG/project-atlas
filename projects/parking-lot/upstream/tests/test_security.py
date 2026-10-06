"""Security primitives tests (Success / Failure / Security)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.security import (
    SigningKey,
    TokenClaims,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "a-very-long-secret-key-for-testing-only-1234567890"
OTHER_SECRET = "another-long-secret-key-for-testing-only-0987654321"
KEY = SigningKey(SECRET)
OTHER_KEY = SigningKey(OTHER_SECRET)


def _claims() -> TokenClaims:
    return TokenClaims("user-1", datetime.now(UTC) + timedelta(minutes=60))


def test_password_hashes_and_verifies():
    hashed = hash_password("s3cret-password")

    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed) is True


def test_wrong_password_is_rejected():
    hashed = hash_password("s3cret-password")

    assert verify_password("wrong-password", hashed) is False


def test_invalid_hash_is_rejected_gracefully():
    assert verify_password("s3cret-password", "not-a-valid-hash") is False


def test_access_token_roundtrip():
    token = create_access_token(_claims(), KEY)

    assert decode_access_token(token, KEY) == "user-1"


def test_invalid_token_raises():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not-a-token", KEY)


def test_token_with_wrong_secret_raises():
    token = create_access_token(_claims(), KEY)

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, OTHER_KEY)


# --- Async (thread-offloaded) hashing -------------------------------------


async def test_async_hash_and_verify_roundtrip():
    from app.core.security import hash_password_async, verify_password_async

    hashed = await hash_password_async("1234")

    assert await verify_password_async("1234", hashed) is True
    assert await verify_password_async("9999", hashed) is False


async def test_async_verify_without_hash_uses_dummy_and_fails():
    from app.core.security import verify_password_async

    assert await verify_password_async("1234", None) is False


async def test_async_verify_runs_off_the_event_loop(monkeypatch):
    import anyio.to_thread

    from app.core import security

    calls = []
    original = anyio.to_thread.run_sync

    async def spy(func, *args, **kwargs):
        calls.append(func)
        return await original(func, *args, **kwargs)

    monkeypatch.setattr(anyio.to_thread, "run_sync", spy)

    await security.verify_password_async("1234", security.hash_password("1234"))

    assert len(calls) == 1
