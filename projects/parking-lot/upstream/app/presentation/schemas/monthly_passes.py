"""Monthly pass DTOs."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class MonthlyPassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    start_date: date
    end_date: date
    amount: int
    active: bool


class MonthlyPassCreate(BaseModel):
    vehicle_id: int
    start_date: date
    end_date: date
    amount: int


class MonthlyPassUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    amount: int | None = None
    active: bool | None = None
