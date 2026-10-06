"""Vehicle repository tests (Success / Failure / Security)."""

import pytest

from app.domain.category import Category
from app.domain.vehicle import Vehicle
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.vehicle_repository import (
    SqlAlchemyVehicleRepository,
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
        yield SqlAlchemyVehicleRepository(session)


async def test_create_and_get_by_plate(repository, category_id):
    await repository.create(
        Vehicle(id=None, plate="ABC123", category_id=category_id, color="red", brand="Mazda")
    )

    fetched = await repository.get_by_plate("ABC123")

    assert fetched is not None
    assert fetched.color == "red"
    assert fetched.brand == "Mazda"


async def test_get_unknown_plate_returns_none(repository):
    assert await repository.get_by_plate("ZZZ999") is None


async def test_update_persists_category(repository, category_id):
    vehicle = await repository.create(
        Vehicle(id=None, plate="ABC123", category_id=category_id)
    )
    vehicle.category_id = category_id

    updated = await repository.update(vehicle)

    assert updated.category_id == category_id


async def test_duplicate_plate_raises_domain_error_and_session_stays_usable(
    repository, category_id
):
    from app.domain.errors import DuplicatePlateError

    await repository.create(Vehicle(id=None, plate="DUP001", category_id=category_id))

    with pytest.raises(DuplicatePlateError):
        await repository.create(
            Vehicle(id=None, plate="DUP001", category_id=category_id)
        )

    assert (await repository.get_by_plate("DUP001")) is not None


async def test_created_by_round_trips(repository, category_id):
    created = await repository.create(
        Vehicle(id=None, plate="AUD002", category_id=category_id, created_by=None)
    )

    assert created.created_by is None


async def test_get_by_ids_returns_only_requested(repository, category_id):
    first = await repository.create(Vehicle(id=None, plate="IDS001", category_id=category_id))
    await repository.create(Vehicle(id=None, plate="IDS002", category_id=category_id))

    fetched = await repository.get_by_ids([first.id, 999_999])

    assert [vehicle.plate for vehicle in fetched] == ["IDS001"]
    assert await repository.get_by_ids([]) == []
