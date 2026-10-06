"""Category repository tests (Success / Failure / Security)."""

import pytest

from app.domain.category import Category
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)


@pytest.fixture
async def repository(session_factory):
    async with session_factory() as session:
        yield SqlAlchemyCategoryRepository(session)


async def test_create_and_get_by_id(repository):
    category = await repository.create(Category(id=None, name="carro"))

    fetched = await repository.get_by_id(category.id)

    assert fetched is not None
    assert fetched.name == "carro"


async def test_get_unknown_name_returns_none(repository):
    assert await repository.get_by_name("camion") is None


async def test_delete_removes_category(repository):
    category = await repository.create(Category(id=None, name="moto"))

    await repository.delete(category.id)

    assert await repository.get_by_id(category.id) is None
