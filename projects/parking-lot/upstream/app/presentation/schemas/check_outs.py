"""Check-out DTOs."""

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.application.check_out_service import ClosedSession
from app.domain.parking_session import SessionStatus


class CheckOutRequest(BaseModel):
    # Must carry an offset (e.g. "...Z" or "...-05:00"); naive -> 422.
    client_exit_time: AwareDatetime | None = None


class CheckOutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    entry_time: datetime
    exit_time: datetime
    status: SessionStatus
    amount_charged: int
    ticket_number: str

    @classmethod
    def from_closed(cls, closed: ClosedSession) -> "CheckOutRead":
        session = closed.session
        return cls(
            id=session.id,
            plate=closed.vehicle.plate,
            entry_time=session.entry_time,
            exit_time=session.exit_time,
            status=session.status,
            amount_charged=session.amount_charged,
            ticket_number=session.ticket_number,
        )
