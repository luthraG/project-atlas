"""SQLAlchemy implementation of the report repository port.

Read-only aggregation over existing tables (parking_sessions, vehicles,
categories) — no new tables, no domain aggregate persistence. Days are
business-local days (`settings.business_timezone`), not UTC days.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement

from app.core.config import settings
from app.domain.parking_session import SessionStatus
from app.domain.report import (
    CategoryOccupancy,
    CategoryRevenue,
    DailyRevenue,
    OccupancyReport,
    RevenueReport,
)
from app.domain.repositories import ReportRepository
from app.infrastructure.models import CategoryModel, ParkingSessionModel, VehicleModel


class local_date(ColumnElement):  # noqa: N801 - SQL-function style name
    """``date(<timestamptz> AT TIME ZONE tz)`` rendered per dialect.

    Postgres uses ``timezone(tz, col)`` (DST-aware). SQLite (test suite
    only) has no tz database, so it applies the zone's current fixed UTC
    offset — exact for zones without DST such as America/Bogota.
    The zone name is validated by ZoneInfo and rendered as a literal so the
    GROUP BY expression is textually identical to the SELECT expression.
    """

    inherit_cache = False
    type = String()

    def __init__(self, column: ColumnElement, tz_name: str):
        ZoneInfo(tz_name)  # raises for unknown/malformed zone names
        self.column = column
        self.tz_name = tz_name

    @property
    def _from_objects(self):
        return self.column._from_objects


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sqlite_offset_modifier(tz_name: str) -> str:
    offset = datetime.now(UTC).astimezone(ZoneInfo(tz_name)).utcoffset()
    return f"{int(offset.total_seconds() // 60):+d} minutes"


@compiles(local_date, "postgresql")
def _compile_local_date_postgres(element, compiler, **kw):
    column = compiler.process(element.column, **kw)
    return f"date(timezone({_sql_string(element.tz_name)}, {column}))"


@compiles(local_date)
def _compile_local_date_default(element, compiler, **kw):
    column = compiler.process(element.column, **kw)
    modifier = _sql_string(_sqlite_offset_modifier(element.tz_name))
    return f"date({column}, {modifier})"


@dataclass(frozen=True)
class _UtcRange:
    start: datetime
    end: datetime


def _local_days_to_utc(start_date: date, end_date: date, zone: ZoneInfo) -> _UtcRange:
    start = datetime.combine(start_date, time.min, tzinfo=zone)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
    return _UtcRange(start.astimezone(UTC), end.astimezone(UTC))


_AMOUNT_SUM = func.coalesce(func.sum(ParkingSessionModel.amount_charged), 0)


class SqlAlchemyReportRepository(ReportRepository):
    def __init__(self, session: AsyncSession, timezone_name: str | None = None):
        self._session = session
        self._tz_name = timezone_name or settings.business_timezone

    async def revenue_by_range(self, start_date: date, end_date: date) -> RevenueReport:
        window = _local_days_to_utc(start_date, end_date, ZoneInfo(self._tz_name))
        total = await self._session.scalar(self._closed_in(select(_AMOUNT_SUM), window))
        return RevenueReport(
            total=int(total or 0),
            by_day=await self._revenue_by_day(window),
            by_category=await self._revenue_by_category(window),
        )

    @staticmethod
    def _closed_in(query: Select, window: _UtcRange) -> Select:
        return query.where(
            ParkingSessionModel.status == SessionStatus.CLOSED.value,
            ParkingSessionModel.exit_time >= window.start,
            ParkingSessionModel.exit_time < window.end,
        )

    async def _revenue_by_day(self, window: _UtcRange) -> list[DailyRevenue]:
        day = local_date(ParkingSessionModel.exit_time, self._tz_name)
        query = self._closed_in(select(day, _AMOUNT_SUM), window)
        result = await self._session.execute(query.group_by(day).order_by(day))
        return [DailyRevenue(date=str(row[0]), amount=int(row[1])) for row in result]

    async def _revenue_by_category(self, window: _UtcRange) -> list[CategoryRevenue]:
        query = self._closed_in(
            select(CategoryModel.id, CategoryModel.name, _AMOUNT_SUM)
            .join(VehicleModel, VehicleModel.id == ParkingSessionModel.vehicle_id)
            .join(CategoryModel, CategoryModel.id == VehicleModel.category_id),
            window,
        )
        result = await self._session.execute(
            query.group_by(CategoryModel.id, CategoryModel.name).order_by(CategoryModel.name)
        )
        return [
            CategoryRevenue(category_id=row[0], category_name=row[1], amount=int(row[2]))
            for row in result
        ]

    async def current_occupancy(self) -> OccupancyReport:
        total_open = await self._session.scalar(
            select(func.count(ParkingSessionModel.id)).where(
                ParkingSessionModel.status == SessionStatus.OPEN.value
            )
        )
        return OccupancyReport(
            total_open=int(total_open or 0), by_category=await self._open_by_category()
        )

    async def _open_by_category(self) -> list[CategoryOccupancy]:
        result = await self._session.execute(
            select(CategoryModel.id, CategoryModel.name, func.count(ParkingSessionModel.id))
            .join(VehicleModel, VehicleModel.id == ParkingSessionModel.vehicle_id)
            .join(CategoryModel, CategoryModel.id == VehicleModel.category_id)
            .where(ParkingSessionModel.status == SessionStatus.OPEN.value)
            .group_by(CategoryModel.id, CategoryModel.name)
            .order_by(CategoryModel.name)
        )
        return [
            CategoryOccupancy(category_id=row[0], category_name=row[1], count=int(row[2]))
            for row in result
        ]
