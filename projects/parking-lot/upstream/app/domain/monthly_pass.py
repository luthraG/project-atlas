"""Monthly pass domain entity and validation."""

from dataclasses import dataclass
from datetime import date

from app.domain.errors import DomainValidationError


@dataclass
class MonthlyPass:
    id: int | None
    vehicle_id: int
    start_date: date
    end_date: date
    amount: int
    active: bool = True


def validate_pass_dates(start_date: date, end_date: date) -> None:
    if end_date <= start_date:
        raise DomainValidationError("end_date must be strictly after start_date")
