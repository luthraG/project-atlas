"""Tariff DTOs."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.tariff import TariffType


class TariffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    type: TariffType
    amount: int
    start_time: str | None
    end_time: str | None
    active: bool


class TariffCreate(BaseModel):
    category_id: int
    type: TariffType
    amount: int
    start_time: str | None = Field(default=None, max_length=5)
    end_time: str | None = Field(default=None, max_length=5)


class TariffUpdate(BaseModel):
    type: TariffType | None = None
    amount: int | None = None
    start_time: str | None = Field(default=None, max_length=5)
    end_time: str | None = Field(default=None, max_length=5)
    active: bool | None = None
