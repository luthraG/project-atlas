"""Shared test fixtures: in-memory SQLite engine, session override, fake clock."""

import os
from contextlib import asynccontextmanager

# Must be set before `app` is imported: Settings refuses the placeholder
# SECRET_KEY outside development/test environments.
os.environ.setdefault("ENVIRONMENT", "test")

from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.domain.user import User, UserRole  # noqa: E402
from app.infrastructure.cache import InMemoryCache  # noqa: E402
from app.infrastructure.database import Base, get_session, session_scope  # noqa: E402
from app.infrastructure.in_memory_login_limiter import (  # noqa: E402
    InMemoryLoginAttemptLimiter,
)
from app.infrastructure.repositories.user_repository import (  # noqa: E402
    SqlAlchemyUserRepository,
)
from app.main import app  # noqa: E402
from app.presentation.deps import get_cache, get_clock, get_login_limiter  # noqa: E402

# 2026-03-10 14:00 UTC == 09:00 America/Bogota: mid-morning, far from both
# UTC and local midnight so no test depends on the wall clock.
DEFAULT_NOW = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)


class FakeClock:
    """Deterministic, manually advanced clock (callable like `system_clock`)."""

    def __init__(self, now: datetime = DEFAULT_NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now = self.now + delta


def _enable_sqlite_savepoints(engine) -> None:
    # pysqlite/aiosqlite defer BEGIN, which breaks SAVEPOINT semantics;
    # SQLAlchemy's documented recipe takes over transaction control.
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _on_begin(connection):
        connection.exec_driver_sql("BEGIN")


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    _enable_sqlite_savepoints(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def login_limiter(clock) -> InMemoryLoginAttemptLimiter:
    return InMemoryLoginAttemptLimiter(clock=clock)


@pytest.fixture
def cache(clock) -> InMemoryCache:
    # Fresh per test: SQLite ids restart at 1, a shared cache would leak.
    return InMemoryCache(clock=clock)


def override_dependencies(session_factory, clock, login_limiter, cache) -> None:
    async def override_get_session():
        async with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_login_limiter] = lambda: login_limiter
    app.dependency_overrides[get_cache] = lambda: cache


@pytest.fixture
def client_for(clock, login_limiter, cache):
    """Open an HTTP client bound to any session factory (SQLite or Postgres)."""

    @asynccontextmanager
    async def _open(factory, raise_app_exceptions: bool = True):
        override_dependencies(factory, clock, login_limiter, cache)
        transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c
        finally:
            app.dependency_overrides.clear()

    return _open


@pytest.fixture
async def client(session_factory, client_for):
    async with client_for(session_factory) as c:
        yield c


@pytest.fixture
async def unsafe_client(client):
    """Like `client`, but unexpected server errors become 500 responses."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def seed_user(session_factory):
    async def _seed(username: str, role: UserRole, pin: str = "1234") -> User:
        async with session_factory() as session:
            user = await SqlAlchemyUserRepository(session).create(
                User(id=None, username=username, display_name=username.title(),
                     role=role, pin_hash=hash_password(pin))
            )
            await session.commit()
            return user

    return _seed


async def _bearer(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/auth/login", json={"username": username, "pin": "1234"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, seed_user) -> dict[str, str]:
    await seed_user("admin", UserRole.ADMIN)
    return await _bearer(client, "admin")


@pytest.fixture
async def operator_headers(client, seed_user) -> dict[str, str]:
    await seed_user("operator", UserRole.OPERATOR)
    return await _bearer(client, "operator")
