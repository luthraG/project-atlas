"""Check-in use cases."""

from collections import defaultdict
from dataclasses import dataclass, field

from app.application.commands import CheckInCommand, NewVehicleData
from app.domain.clock import Clock, system_clock
from app.domain.errors import (
    CategoryNotFoundError,
    DuplicateOpenSessionError,
    DuplicatePlateError,
    VehicleNotFoundError,
    VehicleNotRegisteredError,
)
from app.domain.evidence_photo import EvidencePhoto, PhotoUpload
from app.domain.evidence_storage import EvidenceStoragePort
from app.domain.pagination import Page, PageRequest
from app.domain.parking_session import ParkingSession
from app.domain.repositories import (
    CategoryRepository,
    EvidencePhotoRepository,
    ParkingSessionRepository,
    VehicleRepository,
)
from app.domain.vehicle import Vehicle, normalize_plate

__all__ = [
    "CategoryNotFoundError",
    "CheckInCommand",
    "CheckInPorts",
    "CheckInService",
    "CheckInView",
    "DuplicateOpenSessionError",
    "NewVehicleData",
    "VehicleNotFoundError",
    "VehicleNotRegisteredError",
]


@dataclass
class CheckInPorts:
    vehicles: VehicleRepository
    sessions: ParkingSessionRepository
    photos: EvidencePhotoRepository
    categories: CategoryRepository
    storage: EvidenceStoragePort | None = None  # only needed to store photos


@dataclass
class CheckInView:
    """Read model: an open session with its evidence photos."""

    session: ParkingSession
    plate: str
    photos: list[EvidencePhoto] = field(default_factory=list)


class CheckInService:
    def __init__(self, ports: CheckInPorts, clock: Clock = system_clock):
        self._ports = ports
        self._clock = clock

    async def create_check_in(self, command: CheckInCommand) -> CheckInView:
        vehicle = await self._resolve_vehicle(command)
        if await self._ports.sessions.get_open_by_vehicle_id(vehicle.id) is not None:
            raise DuplicateOpenSessionError()
        session = await self._ports.sessions.create(
            ParkingSession(id=None, vehicle_id=vehicle.id, operator_id=command.operator_id,
                           entry_time=self._clock())
        )
        # Files are written only after every domain check has passed.
        photos = await self._store_photos(session, command.photos)
        return CheckInView(session, vehicle.plate, photos)

    async def list_open(self, page: PageRequest) -> Page[CheckInView]:
        sessions = await self._ports.sessions.list_open_page(page)
        ids = [session.id for session in sessions.items]
        by_session: dict[int, list[EvidencePhoto]] = defaultdict(list)
        for photo in await self._ports.photos.list_by_session_ids(ids):
            by_session[photo.session_id].append(photo)
        vehicles = await self._ports.vehicles.get_by_ids(ids)
        plates = {vehicle.id: vehicle.plate for vehicle in vehicles}
        views = [CheckInView(s, plates[s.vehicle_id], by_session.get(s.id, []))
                 for s in sessions.items]
        return Page(views, sessions.total)

    async def _store_photos(
        self, session: ParkingSession, photos: list[PhotoUpload]
    ) -> list[EvidencePhoto]:
        saved: list[str] = []
        try:
            for photo in photos:
                saved.append(await self._ports.storage.save(photo.content, photo.extension))
            return [await self._record_photo(session, path) for path in saved]
        except BaseException:
            # Compensation: never leave files without their DB rows.
            await self._delete_files(saved)
            raise

    async def _record_photo(self, session: ParkingSession, path: str) -> EvidencePhoto:
        return await self._ports.photos.create(
            EvidencePhoto(id=None, session_id=session.id, file_path=path, taken_at=self._clock())
        )

    async def _delete_files(self, paths: list[str]) -> None:
        for path in paths:
            await self._ports.storage.delete(path)

    async def _resolve_vehicle(self, command: CheckInCommand) -> Vehicle:
        plate = normalize_plate(command.plate)
        vehicle = await self._ports.vehicles.get_by_plate(plate)
        if vehicle is not None:
            return vehicle
        return await self._register_vehicle(plate, command)

    async def _register_vehicle(self, plate: str, command: CheckInCommand) -> Vehicle:
        data = command.new_vehicle
        if data.category_id is None:
            raise VehicleNotRegisteredError()
        if await self._ports.categories.get_by_id(data.category_id) is None:
            raise CategoryNotFoundError()
        try:
            return await self._ports.vehicles.create(
                Vehicle(id=None, plate=plate, category_id=data.category_id, color=data.color,
                        brand=data.brand, created_by=command.operator_id)
            )
        except DuplicatePlateError:
            # Another operator registered the same new plate concurrently.
            return await self._existing_vehicle(plate)

    async def _existing_vehicle(self, plate: str) -> Vehicle:
        vehicle = await self._ports.vehicles.get_by_plate(plate)
        if vehicle is None:
            raise VehicleNotFoundError()
        return vehicle
