"""Password hashing (Argon2id) and JWT primitives."""

from dataclasses import dataclass
from datetime import datetime
from functools import cache

import anyio.to_thread
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


@cache
def _dummy_hash() -> str:
    return _password_hasher.hash("timing-equalizer")


async def hash_password_async(password: str) -> str:
    """Argon2 is CPU-bound (~50-100 ms): keep it off the event loop."""
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(password: str, hashed: str | None) -> bool:
    """Verify off the event loop; a missing hash still costs one verify.

    Verifying against a dummy hash when the user does not exist equalizes
    response time so usernames cannot be enumerated by timing.
    """
    target = hashed if hashed is not None else _dummy_hash()
    ok = await anyio.to_thread.run_sync(verify_password, password, target)
    return ok and hashed is not None


@dataclass(frozen=True)
class SigningKey:
    secret: str
    algorithm: str = "HS256"


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    expires_at: datetime


def create_access_token(claims: TokenClaims, key: SigningKey) -> str:
    payload = {"sub": claims.subject, "exp": claims.expires_at}
    return jwt.encode(payload, key.secret, algorithm=key.algorithm)


def decode_access_token(token: str, key: SigningKey) -> str:
    """Verified subject; raises jwt.PyJWTError when invalid or expired."""
    payload = jwt.decode(token, key.secret, algorithms=[key.algorithm])
    return str(payload["sub"])
