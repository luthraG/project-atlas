"""CheckInService tests: race translation and photo compensation (B-UQ/B-UP)."""

import pytest

from app.application.check_in_service import (
    CheckInCommand,
    CheckInPorts,
    CheckInService,
    DuplicateOpenSessionError,
    NewVehicleData,
    VehicleNotRegisteredError,
)
from app.domain.category import Category
from app.domain.evidence_photo import PhotoUpload
from app.domain.evidence_storage import EvidenceStoragePort
from app.domain.user import User, UserRole
from app.domain.vehicle import Vehicle
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.evidence_photo_repository import (
    SqlAlchemyEvidencePhotoRepository,
)
from app.infrastructure.repositories.parking_session_repository import (
    SqlAlchemyParkingSessionRepository,
)
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.repositories.vehicle_repository import (
    SqlAlchemyVehicleRepository,
)

PHOTO = PhotoUpload(content=b"\xff\xd8\xffdata", extension=".jpg")


class RecordingStorage(EvidenceStoragePort):
    def __init__(self):
        self.saved: list[str] = []
        self.deleted: list[str] = []

    async def save(self, content: bytes, extension: str) -> str:
        path = f"file-{len(self.saved)}{extension}"
        self.saved.append(path)
        return path

    async def delete(self, path: str) -> None:
        self.deleted.append(path)


class StaleVehicleReads(SqlAlchemyVehicleRepository):
    """First plate lookup misses, as if another operator inserted it just now."""

    def __init__(self, session):
        super().__init__(session)
        self._missed = False

    async def get_by_plate(self, plate):
        if not self._missed:
            self._missed = True
            return None
        return await super().get_by_plate(plate)


class StaleOpenSessionReads(SqlAlchemyParkingSessionRepository):
    async def get_open_by_vehicle_id(self, vehicle_id):
        return None


class FailingPhotoRepository(SqlAlchemyEvidencePhotoRepository):
    async def create(self, photo):
        raise RuntimeError("db down")


@pytest.fixture
async def seeded(session_factory):
    async with session_factory() as session:
        category = await SqlAlchemyCategoryRepository(session).create(
            Category(id=None, name="carro")
        )
        operator = await SqlAlchemyUserRepository(session).create(
            User(id=None, username="op", display_name="Op",
                 role=UserRole.OPERATOR, pin_hash="hash")
        )
        await session.commit()
        return {"category_id": category.id, "operator_id": operator.id}


def _ports(session, storage, **overrides):
    defaults = {
        "vehicles": SqlAlchemyVehicleRepository(session),
        "sessions": SqlAlchemyParkingSessionRepository(session),
        "photos": SqlAlchemyEvidencePhotoRepository(session),
        "categories": SqlAlchemyCategoryRepository(session),
        "storage": storage,
    }
    defaults.update(overrides)
    return CheckInPorts(**defaults)


async def test_concurrent_new_plate_reuses_existing_vehicle(session_factory, seeded, clock):
    async with session_factory() as session:
        existing = await SqlAlchemyVehicleRepository(session).create(
            Vehicle(id=None, plate="RACE01", category_id=seeded["category_id"])
        )
        ports = _ports(session, RecordingStorage(), vehicles=StaleVehicleReads(session))
        command = CheckInCommand(
            plate="RACE01",
            operator_id=seeded["operator_id"],
            new_vehicle=NewVehicleData(category_id=seeded["category_id"]),
        )

        created = (await CheckInService(ports, clock).create_check_in(command)).session

        assert created.vehicle_id == existing.id
        assert created.entry_time == clock.now


async def test_concurrent_open_session_is_translated_to_conflict(
    session_factory, seeded, clock
):
    async with session_factory() as session:
        await SqlAlchemyVehicleRepository(session).create(
            Vehicle(id=None, plate="RACE02", category_id=seeded["category_id"])
        )
        ports = _ports(session, RecordingStorage(),
                       sessions=StaleOpenSessionReads(session))
        service = CheckInService(ports, clock)
        command = CheckInCommand(plate="RACE02", operator_id=seeded["operator_id"])
        await service.create_check_in(command)

        with pytest.raises(DuplicateOpenSessionError):
            await service.create_check_in(command)


async def test_photos_saved_only_after_validation(session_factory, seeded, clock):
    storage = RecordingStorage()
    async with session_factory() as session:
        command = CheckInCommand(
            plate="UNKNOWN", operator_id=seeded["operator_id"], photos=[PHOTO]
        )

        with pytest.raises(VehicleNotRegisteredError):
            await CheckInService(_ports(session, storage), clock).create_check_in(command)

    assert storage.saved == []


async def test_saved_photos_are_deleted_when_persistence_fails(
    session_factory, seeded, clock
):
    """Compensation: no orphan files when a later step fails."""
    storage = RecordingStorage()
    async with session_factory() as session:
        await SqlAlchemyVehicleRepository(session).create(
            Vehicle(id=None, plate="COMP01", category_id=seeded["category_id"])
        )
        ports = _ports(session, storage, photos=FailingPhotoRepository(session))
        command = CheckInCommand(
            plate="COMP01", operator_id=seeded["operator_id"], photos=[PHOTO, PHOTO]
        )

        with pytest.raises(RuntimeError):
            await CheckInService(ports, clock).create_check_in(command)

    assert storage.saved == ["file-0.jpg", "file-1.jpg"]
    assert storage.deleted == storage.saved
