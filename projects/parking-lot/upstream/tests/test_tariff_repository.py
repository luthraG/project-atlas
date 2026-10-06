"""Tariff repository tests (Success / Failure / Security)."""

import pytest

from app.domain.category import Category
from app.domain.tariff import Tariff, TariffType
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.tariff_repository import (
    SqlAlchemyTariffRepository,
)


@pytest.fixture
async def category_id(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyCategoryRepository(session)
        category = await repository.create(Category(id=None, name="carro"))
        await session.commit()
        return category.id


@pytest.fixture
async def repository(session_factory):
    async with session_factory() as session:
        yield SqlAlchemyTariffRepository(session)


async def test_create_and_get_by_id(repository, category_id):
    tariff = await repository.create(
        Tariff(
            id=None,
            category_id=category_id,
            type=TariffType.HOURLY,
            amount=3000,
            start_time=None,
            end_time=None,
        )
    )

    fetched = await repository.get_by_id(tariff.id)

    assert fetched is not None
    assert fetched.type == TariffType.HOURLY
    assert fetched.amount == 3000


async def test_get_unknown_returns_none(repository):
    assert await repository.get_by_id(999) is None


async def test_nightly_tariff_preserves_window(repository, category_id):
    tariff = await repository.create(
        Tariff(
            id=None,
            category_id=category_id,
            type=TariffType.NIGHTLY,
            amount=5000,
            start_time="18:00",
            end_time="06:00",
        )
    )

    fetched = await repository.get_by_id(tariff.id)

    assert fetched.start_time == "18:00"
    assert fetched.end_time == "06:00"
