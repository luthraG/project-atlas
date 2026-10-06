"""Command / parameter objects passed from presentation to use cases."""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.evidence_photo import PhotoUpload
from app.domain.user import UserRole


@dataclass
class NewVehicleData:
    """Data used to auto-register a vehicle whose plate is unknown."""

    category_id: int | None = None
    color: str | None = None
    brand: str | None = None


@dataclass
class CheckInCommand:
    plate: str
    operator_id: int
    photos: list[PhotoUpload] = field(default_factory=list)
    new_vehicle: NewVehicleData = field(default_factory=NewVehicleData)


@dataclass(frozen=True)
class CheckOutCommand:
    session_id: int
    client_exit_time: datetime | None = None


@dataclass(frozen=True)
class CreateUserCommand:
    username: str
    display_name: str
    role: UserRole
    pin: str


@dataclass(frozen=True)
class UserPatch:
    display_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


@dataclass(frozen=True)
class IdempotentRequest:
    key: str
    user_id: int
    endpoint: str  # e.g. "POST /api/check-outs/5"


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: str  # JSON document
