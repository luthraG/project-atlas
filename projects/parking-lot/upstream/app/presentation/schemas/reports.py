"""Report DTOs."""

from dataclasses import asdict
from datetime import date

from pydantic import BaseModel

from app.domain.report import OccupancyReport, RevenueReport


class DailyRevenueRead(BaseModel):
    date: str
    amount: int


class CategoryRevenueRead(BaseModel):
    category_id: int
    category_name: str
    amount: int


class RevenueReportRead(BaseModel):
    start_date: date
    end_date: date
    total: int
    by_day: list[DailyRevenueRead]
    by_category: list[CategoryRevenueRead]

    @classmethod
    def from_report(cls, report: RevenueReport, period: tuple[date, date]) -> "RevenueReportRead":
        return cls.model_validate(
            {**asdict(report), "start_date": period[0], "end_date": period[1]}
        )


class CategoryOccupancyRead(BaseModel):
    category_id: int
    category_name: str
    count: int


class OccupancyReportRead(BaseModel):
    total_open: int
    by_category: list[CategoryOccupancyRead]

    @classmethod
    def from_report(cls, report: OccupancyReport) -> "OccupancyReportRead":
        return cls.model_validate(asdict(report))
