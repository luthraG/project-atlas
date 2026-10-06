"""Report use cases: thin pass-through to the ReportRepository port."""

from datetime import date

from app.domain.errors import InvalidReportRangeError
from app.domain.report import OccupancyReport, RevenueReport
from app.domain.repositories import ReportRepository

__all__ = ["InvalidReportRangeError", "ReportService"]


class ReportService:
    def __init__(self, reports: ReportRepository):
        self._reports = reports

    async def get_revenue_report(
        self, start_date: date, end_date: date
    ) -> RevenueReport:
        if start_date > end_date:
            raise InvalidReportRangeError(
                f"start_date {start_date} is after end_date {end_date}"
            )
        return await self._reports.revenue_by_range(start_date, end_date)

    async def get_occupancy_report(self) -> OccupancyReport:
        return await self._reports.current_occupancy()
