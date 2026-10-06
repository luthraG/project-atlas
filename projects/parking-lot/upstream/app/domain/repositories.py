"""Repository ports for the parking domain."""

from abc import ABC, abstractmethod
from datetime import date

from app.domain.category import Category
from app.domain.evidence_photo import EvidencePhoto
from app.domain.monthly_pass import MonthlyPass
from app.domain.pagination import Page, PageRequest
from app.domain.parking_session import ParkingSession
from app.domain.report import OccupancyReport, RevenueReport
from app.domain.tariff import Tariff
from app.domain.user import User
from app.domain.vehicle import Vehicle


class UserRepository(ABC):
    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[User]:
        raise NotImplementedError

    @abstractmethod
    async def list_page(self, page: PageRequest) -> Page[User]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, user: User) -> User:
        raise NotImplementedError

    @abstractmethod
    async def update(self, user: User) -> User:
        raise NotImplementedError


class CategoryRepository(ABC):
    @abstractmethod
    async def get_by_name(self, name: str) -> Category | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, category_id: int) -> Category | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[Category]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, category: Category) -> Category:
        raise NotImplementedError

    @abstractmethod
    async def update(self, category: Category) -> Category:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, category_id: int) -> None:
        raise NotImplementedError


class TariffRepository(ABC):
    @abstractmethod
    async def get_by_id(self, tariff_id: int) -> Tariff | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[Tariff]:
        raise NotImplementedError

    @abstractmethod
    async def list_by_category(self, category_id: int) -> list[Tariff]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, tariff: Tariff) -> Tariff:
        raise NotImplementedError

    @abstractmethod
    async def update(self, tariff: Tariff) -> Tariff:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, tariff_id: int) -> None:
        raise NotImplementedError


class VehicleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, vehicle_id: int) -> Vehicle | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_plate(self, plate: str) -> Vehicle | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_ids(self, vehicle_ids: list[int]) -> list[Vehicle]:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[Vehicle]:
        raise NotImplementedError

    @abstractmethod
    async def list_page(self, page: PageRequest) -> Page[Vehicle]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, vehicle: Vehicle) -> Vehicle:
        raise NotImplementedError

    @abstractmethod
    async def update(self, vehicle: Vehicle) -> Vehicle:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, vehicle_id: int) -> None:
        raise NotImplementedError


class ParkingSessionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, session_id: int) -> ParkingSession | None:
        raise NotImplementedError

    @abstractmethod
    async def get_open_by_vehicle_id(
        self, vehicle_id: int
    ) -> ParkingSession | None:
        raise NotImplementedError

    @abstractmethod
    async def list_open(self) -> list[ParkingSession]:
        raise NotImplementedError

    @abstractmethod
    async def list_open_page(self, page: PageRequest) -> Page[ParkingSession]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, session: ParkingSession) -> ParkingSession:
        """Raises DuplicateOpenSessionError if the vehicle already has one."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, session: ParkingSession) -> ParkingSession:
        raise NotImplementedError

    @abstractmethod
    async def close(self, session: ParkingSession) -> ParkingSession | None:
        """Atomically close an OPEN session; None if it was already closed."""
        raise NotImplementedError


class EvidencePhotoRepository(ABC):
    @abstractmethod
    async def list_by_session_id(self, session_id: int) -> list[EvidencePhoto]:
        raise NotImplementedError

    @abstractmethod
    async def list_by_session_ids(self, session_ids: list[int]) -> list[EvidencePhoto]:
        """All photos of the given sessions in ONE query (avoids N+1)."""
        raise NotImplementedError

    @abstractmethod
    async def create(self, photo: EvidencePhoto) -> EvidencePhoto:
        raise NotImplementedError


class MonthlyPassRepository(ABC):
    @abstractmethod
    async def get_by_id(self, pass_id: int) -> MonthlyPass | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> list[MonthlyPass]:
        raise NotImplementedError

    @abstractmethod
    async def list_by_vehicle(self, vehicle_id: int) -> list[MonthlyPass]:
        raise NotImplementedError

    @abstractmethod
    async def get_active_for_vehicle(
        self, vehicle_id: int, on_date: date
    ) -> MonthlyPass | None:
        raise NotImplementedError

    @abstractmethod
    async def list_page(self, page: PageRequest) -> Page[MonthlyPass]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, monthly_pass: MonthlyPass) -> MonthlyPass:
        raise NotImplementedError

    @abstractmethod
    async def update(self, monthly_pass: MonthlyPass) -> MonthlyPass:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, pass_id: int) -> None:
        raise NotImplementedError


class ReportRepository(ABC):
    @abstractmethod
    async def revenue_by_range(
        self, start_date: date, end_date: date
    ) -> RevenueReport:
        raise NotImplementedError

    @abstractmethod
    async def current_occupancy(self) -> OccupancyReport:
        raise NotImplementedError
