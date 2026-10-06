"""Check-in DTOs."""

from datetime import datetime

from fastapi import Form
from pydantic import BaseModel, ConfigDict, Field

from app.application.check_in_service import CheckInView
from app.application.commands import CheckInCommand, NewVehicleData
from app.domain.evidence_photo import PhotoUpload
from app.domain.parking_session import SessionStatus


class EvidencePhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str
    taken_at: datetime


class CheckInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    plate: str
    operator_id: int
    entry_time: datetime
    status: SessionStatus
    photos: list[EvidencePhotoRead] = []
    photo_count: int

    @classmethod
    def from_view(cls, view: CheckInView) -> "CheckInRead":
        session = view.session
        return cls(
            id=session.id,
            vehicle_id=session.vehicle_id,
            plate=view.plate,
            operator_id=session.operator_id,
            entry_time=session.entry_time,
            status=session.status,
            photos=[EvidencePhotoRead.model_validate(photo) for photo in view.photos],
            photo_count=len(view.photos),
        )


class CheckInForm(BaseModel):
    """Multipart form fields of POST /check-ins (sizes mirror DB columns)."""

    plate: str = Field(min_length=1, max_length=20)
    category_id: int | None = None
    color: str | None = Field(default=None, max_length=30)
    brand: str | None = Field(default=None, max_length=50)

    @classmethod
    def as_form(
        cls,
        plate: str = Form(..., max_length=20),
        category_id: int | None = Form(default=None),
        color: str | None = Form(default=None, max_length=30),
        brand: str | None = Form(default=None, max_length=50),
    ) -> "CheckInForm":
        return cls(plate=plate, category_id=category_id, color=color, brand=brand)

    def to_command(self, operator_id: int, photos: list[PhotoUpload]) -> CheckInCommand:
        return CheckInCommand(
            plate=self.plate,
            operator_id=operator_id,
            photos=photos,
            new_vehicle=NewVehicleData(self.category_id, self.color, self.brand),
        )
