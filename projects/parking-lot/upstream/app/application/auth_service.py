"""Authentication use cases."""

from dataclasses import dataclass

from app.domain.errors import InvalidCredentialsError, TooManyLoginAttemptsError
from app.domain.login_attempts import LoginAttemptLimiter
from app.domain.ports import PasswordHasher, TokenIssuer
from app.domain.repositories import UserRepository
from app.domain.user import User

__all__ = ["AuthPorts", "AuthService", "LoginAttempt", "TooManyLoginAttemptsError"]


@dataclass(frozen=True)
class LoginAttempt:
    username: str
    pin: str
    client_ip: str

    @property
    def throttle_key(self) -> str:
        return f"{self.client_ip}|{self.username.strip().lower()}"


@dataclass(frozen=True)
class AuthPorts:
    users: UserRepository
    limiter: LoginAttemptLimiter
    hasher: PasswordHasher
    tokens: TokenIssuer


class AuthService:
    def __init__(self, ports: AuthPorts):
        self._ports = ports

    async def login(self, attempt: LoginAttempt) -> User:
        limiter = self._ports.limiter
        retry_after = await limiter.retry_after_seconds(attempt.throttle_key)
        if retry_after > 0:
            raise TooManyLoginAttemptsError(retry_after)
        user = await self._verified_user(attempt)
        if user is None:
            await limiter.record_failure(attempt.throttle_key)
            raise InvalidCredentialsError()
        await limiter.reset(attempt.throttle_key)
        return user

    async def _verified_user(self, attempt: LoginAttempt) -> User | None:
        user = await self._ports.users.get_by_username(attempt.username)
        usable = user is not None and user.is_active
        # Always run one Argon2 verify (dummy hash when unusable): equal timing.
        hashed = user.pin_hash if usable else None
        ok = await self._ports.hasher.verify(attempt.pin, hashed)
        return user if ok and usable else None

    def issue_token(self, user: User) -> str:
        return self._ports.tokens.issue(user.username)

