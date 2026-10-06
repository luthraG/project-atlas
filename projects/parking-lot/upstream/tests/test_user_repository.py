"""User repository tests (Success / Failure / Security)."""

import pytest

from app.core.security import hash_password
from app.domain.user import User, UserRole
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository


@pytest.fixture
async def repository(session_factory):
    async with session_factory() as session:
        yield SqlAlchemyUserRepository(session)


async def test_create_and_get_by_username(repository):
    await repository.create(
        User(
            id=None,
            username="juan",
            display_name="Juan Perez",
            role=UserRole.OPERATOR,
            pin_hash=hash_password("1234"),
        )
    )

    fetched = await repository.get_by_username("juan")

    assert fetched is not None
    assert fetched.username == "juan"
    assert fetched.role == UserRole.OPERATOR


async def test_get_unknown_username_returns_none(repository):
    assert await repository.get_by_username("nobody") is None


async def test_repository_stores_hash_not_plaintext(repository):
    user = await repository.create(
        User(
            id=None,
            username="admin",
            display_name="Admin",
            role=UserRole.ADMIN,
            pin_hash=hash_password("9876"),
        )
    )

    assert user.pin_hash != "9876"
    assert "9876" not in user.pin_hash
