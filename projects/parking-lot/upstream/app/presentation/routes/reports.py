"""Report endpoints (revenue, occupancy) — admin only."""

from datetime import date

from fastapi import APIRouter, Depends

from app.application.report_service import ReportService
from app.presentation.deps import get_report_service, require_admin
from app.presentation.schemas import OccupancyReportRead, RevenueReportRead

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_admin)])


@router.get("/revenue", response_model=RevenueReportRead)
async def get_revenue_report(
    start_date: date,
    end_date: date,
    service: ReportService = Depends(get_report_service),
) -> RevenueReportRead:
    report = await service.get_revenue_report(start_date, end_date)
    return RevenueReportRead.from_report(report, (start_date, end_date))


@router.get("/occupancy", response_model=OccupancyReportRead)
async def get_occupancy_report(
    service: ReportService = Depends(get_report_service),
) -> OccupancyReportRead:
    return OccupancyReportRead.from_report(await service.get_occupancy_report())
