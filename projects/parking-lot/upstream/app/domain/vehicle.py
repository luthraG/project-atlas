"""Vehicle domain entity and plate normalization."""

from dataclasses import dataclass

from app.domain.errors import DomainValidationError


@dataclass
class Vehicle:
    id: int | None
    plate: str
    category_id: int
    color: str | None = None
    brand: str | None = None
    created_by: int | None = None  # operator who auto-registered it


def normalize_plate(plate: str) -> str:
    value = "".join(plate.split()).upper()
    if not value:
        raise DomainValidationError("Plate must not be empty")
    return value
