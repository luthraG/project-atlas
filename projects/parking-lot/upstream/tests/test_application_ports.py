"""Application services depend only on injected ports (no global settings)."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app.application.auth_service import AuthPorts, AuthService, LoginAttempt
from app.application.check_out_service import (
    CheckOutContext,
    CheckOutRepositories,
    CheckOutService,
)
from app.application.commands import CheckOutCommand, CreateUserCommand
from app.application.user_service import UserService
from app.domain.billing import FareCalculator
from app.domain.clock import system_clock
from app.domain.errors import (
    DuplicateUsernameError,
    InvalidCredentialsError,
    InvalidTokenError,
    VehicleNotFoundError,
)
from app.domain.parking_session import ParkingSession
from app.domain.ports import PasswordHasher, TokenIssuer
from app.domain.user import User, UserRole
from app.infrastructure.in_memory_login_limiter import InMemoryLoginAttemptLimiter
from app.infrastructure.security import JwtConfig, JwtTokenIssuer


class PlainHasher(PasswordHasher):
    def __init__(self):
        self.verified: list[str | None] = []

    async def hash(self, plain: str) -> str:
        return f"hashed:{plain}"

    async def verify(self, plain: str, hashed: str | None) -> bool:
        self.verified.append(hashed)
        return hashed == f"hashed:{plain}"


class FixedIssuer(TokenIssuer):
    def issue(self, subject: str) -> str:
        return f"token-for-{subject}"

    def subject_of(self, token: str) -> str:
        return token.removeprefix("token-for-")


class MemoryUsers:
    def __init__(self, *users: User):
        self._users = {user.username: user for user in users}

    async def get_by_username(self, username):
        return self._users.get(username)

    async def create(self, user):
        user.id = len(self._users) + 1
        self._users[user.username] = user
        return user


def _user(pin_hash="hashed:1234", active=True) -> User:
    return User(id=1, username="ana", display_name="Ana", role=UserRole.OPERATOR,
                pin_hash=pin_hash, is_active=active)


def _auth(users, hasher, clock) -> AuthService:
    limiter = InMemoryLoginAttemptLimiter(clock=clock)
    return AuthService(AuthPorts(users, limiter, hasher, FixedIssuer()))


async def test_login_uses_injected_hasher_and_issuer(clock):
    service = _auth(MemoryUsers(_user()), PlainHasher(), clock)

    user = await service.login(LoginAttempt("ana", "1234", "1.1.1.1"))

    assert user.username == "ana"
    assert service.issue_token(user) == "token-for-ana"


async def test_login_with_wrong_pin_raises_invalid_credentials(clock):
    service = _auth(MemoryUsers(_user()), PlainHasher(), clock)

    with pytest.raises(InvalidCredentialsError):
        await service.login(LoginAttempt("ana", "9999", "1.1.1.1"))


async def test_inactive_user_still_costs_one_verify(clock):
    hasher = PlainHasher()
    service = _auth(MemoryUsers(_user(active=False)), hasher, clock)

    with pytest.raises(InvalidCredentialsError):
        await service.login(LoginAttempt("ana", "1234", "1.1.1.1"))

    assert hasher.verified == [None]


async def test_user_service_hashes_through_port():
    users = MemoryUsers()
    service = UserService(users, PlainHasher())

    created = await service.create(CreateUserCommand("bob", "Bob", UserRole.ADMIN, "4321"))

    assert created.pin_hash == "hashed:4321"
    with pytest.raises(DuplicateUsernameError):
        await service.create(CreateUserCommand("bob", "Bob", UserRole.ADMIN, "4321"))


def test_jwt_issuer_round_trip_and_rejects_tampering():
    config = JwtConfig(secret="x" * 40, algorithm="HS256", expires_minutes=5)
    issuer = JwtTokenIssuer(config)

    token = issuer.issue("ana")

    assert issuer.subject_of(token) == "ana"
    with pytest.raises(InvalidTokenError):
        issuer.subject_of(token + "x")


def test_jwt_issuer_rejects_expired_token():
    config = JwtConfig(secret="x" * 40, algorithm="HS256", expires_minutes=5)
    past = system_clock() - timedelta(minutes=10)
    token = JwtTokenIssuer(config, clock=lambda: past).issue("ana")

    with pytest.raises(InvalidTokenError):
        JwtTokenIssuer(config).subject_of(token)


class _Sessions:
    def __init__(self, session):
        self._session = session

    async def get_by_id(self, _):
        return self._session


class _NoVehicles:
    async def get_by_id(self, _):
        return None


async def test_check_out_with_missing_vehicle_is_not_found(clock):
    session = ParkingSession(id=7, vehicle_id=99, operator_id=1,
                             entry_time=clock.now - timedelta(hours=1))
    repos = CheckOutRepositories(_Sessions(session), _NoVehicles(), None, None)
    context = CheckOutContext(FareCalculator(ZoneInfo("America/Bogota")), clock)
    service = CheckOutService(repos, context)

    with pytest.raises(VehicleNotFoundError):
        await service.close_session(CheckOutCommand(session_id=7))
