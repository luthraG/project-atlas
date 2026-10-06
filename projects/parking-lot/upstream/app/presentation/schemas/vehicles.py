"""Vehicle DTOs."""

from pydantic import BaseModel, ConfigDict, Field


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    category_id: int
    color: str | None
    brand: str | None
    # Audit: operator that auto-registered it at check-in (None if admin-created).
    created_by: int | None = None


class VehicleCreate(BaseModel):
    plate: str = Field(min_length=1, max_length=20)
    category_id: int
    color: str | None = Field(default=None, max_length=30)
    brand: str | None = Field(default=None, max_length=50)


class VehicleUpdate(BaseModel):
    category_id: int | None = None
    color: str | None = Field(default=None, max_length=30)
    brand: str | None = Field(default=None, max_length=50)
