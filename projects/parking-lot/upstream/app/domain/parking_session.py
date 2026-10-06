"""Parking session domain entity and status."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class ParkingSession:
    id: int | None
    vehicle_id: int
    operator_id: int
    entry_time: datetime
    status: SessionStatus = SessionStatus.OPEN
    exit_time: datetime | None = None
    amount_charged: int | None = None
    ticket_number: str | None = None
