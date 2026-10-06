"""Pure fare calculation for a parking stay (no I/O, no settings).

Calendar days and night windows are evaluated in the business timezone
handed to `FareCalculator`: aware inputs in any offset are converted before
splitting, so "22:00-06:00" means local night. See
`openspec/specs/billing/spec.md` for the rounding/cap granularity rationale.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.category_tariffs import CategoryTariffs
from app.domain.errors import InvalidBillingPeriodError, MissingHourlyTariffError
from app.domain.tariff import Tariff, TariffType

_SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class StayPeriod:
    """Parameter object: the interval being priced."""

    entry_time: datetime
    exit_time: datetime
    has_active_monthly_pass: bool = False


@dataclass(frozen=True)
class _DaySegment:
    day: date
    start: datetime
    end: datetime


class FareCalculator:
    """Computes the charge for a parking stay from a category's tariffs."""

    def __init__(self, zone: ZoneInfo):
        self._zone = zone

    def calculate_fare(self, tariffs: CategoryTariffs, period: StayPeriod) -> Decimal:
        entry_local, exit_local = self._to_local(period)
        if period.has_active_monthly_pass:
            return Decimal("0")
        total = sum(
            (_charge_for_day(segment, tariffs)
             for segment in _split_by_calendar_day(entry_local, exit_local)),
            Decimal("0"),
        )
        # Defense in depth: never return a negative charge.
        return max(total, Decimal("0"))

    def local_date(self, instant: datetime) -> date:
        """Business-local calendar date of an aware instant."""
        return instant.astimezone(self._zone).date()

    def _to_local(self, period: StayPeriod) -> tuple[datetime, datetime]:
        entry_time, exit_time = period.entry_time, period.exit_time
        if entry_time.tzinfo is None or exit_time.tzinfo is None:
            raise InvalidBillingPeriodError("entry_time and exit_time must be timezone-aware")
        if exit_time <= entry_time:
            raise InvalidBillingPeriodError("exit_time must be after entry_time")
        return entry_time.astimezone(self._zone), exit_time.astimezone(self._zone)


def select_category_tariffs(category_id: int, rows: list[Tariff]) -> CategoryTariffs:
    """Bundle a category's first active hourly/daily/nightly rows."""
    hourly = _first_active(rows, TariffType.HOURLY)
    if hourly is None:
        raise MissingHourlyTariffError()
    return CategoryTariffs(
        category_id=category_id,
        hourly=hourly,
        daily=_first_active(rows, TariffType.DAILY),
        nightly=_first_active(rows, TariffType.NIGHTLY),
    )


def _first_active(rows: list[Tariff], tariff_type: TariffType) -> Tariff | None:
    for row in rows:
        if row.type == tariff_type and row.active:
            return row
    return None


def _split_by_calendar_day(entry_time: datetime, exit_time: datetime) -> list[_DaySegment]:
    """Split [entry_time, exit_time) into one sub-interval per calendar day.

    Calendar day = midnight-to-midnight in the datetimes' own tzinfo; the
    caller (`FareCalculator`) converts to the business zone first.
    """
    segments: list[_DaySegment] = []
    cursor = entry_time
    while cursor < exit_time:
        day = cursor.date()
        if day == exit_time.date():
            # Last (or only) day: the stay ends before the next midnight.
            segments.append(_DaySegment(day=day, start=cursor, end=exit_time))
            break
        next_midnight = datetime.combine(day + timedelta(days=1), time.min)
        segments.append(_DaySegment(day=day, start=cursor, end=next_midnight))
        cursor = next_midnight
    return segments


def _charge_for_day(segment: _DaySegment, tariffs: CategoryTariffs) -> Decimal:
    """Charge for one calendar day, capped by the daily tariff.

    Rounding granularity: ceil is applied ONCE PER CALENDAR DAY, PER RATE
    TYPE (night minutes summed then ceiled once; day minutes likewise). Not
    per disjoint sub-interval (a midnight-wrapping window would double-round)
    and not pooled across days (that would break the per-day cap, which
    applies independently to every day touched, partial days included).
    """
    night_seconds, day_seconds = _split_seconds(segment, tariffs.nightly)
    night_rate = _clamped_amount(tariffs.nightly.amount) if tariffs.nightly else Decimal("0")
    charge = Decimal(_ceil_hours(day_seconds)) * _clamped_amount(tariffs.hourly.amount)
    if tariffs.daily is not None:
        charge = min(charge, _clamped_amount(tariffs.daily.amount))
    return charge + Decimal(_ceil_hours(night_seconds)) * night_rate


def _split_seconds(segment: _DaySegment, nightly: Tariff | None) -> tuple[int, int]:
    """Return (night_seconds, day_seconds) for this calendar-day segment."""
    total_seconds = _to_seconds(segment.end - segment.start)

    if nightly is None:
        return 0, total_seconds

    night_seconds = 0
    for window_start, window_end in _night_windows_for_day(segment, nightly):
        overlap_start = max(segment.start, window_start)
        overlap_end = min(segment.end, window_end)
        if overlap_end > overlap_start:
            night_seconds += _to_seconds(overlap_end - overlap_start)

    return night_seconds, total_seconds - night_seconds


def _night_windows_for_day(
    segment: _DaySegment, nightly: Tariff
) -> list[tuple[datetime, datetime]]:
    """Absolute datetime ranges of the night window inside this calendar day.

    A window that crosses midnight (e.g. "22:00"-"06:00") shows up as two
    disjoint ranges within a single calendar day: the tail of the previous
    night (00:00 -> end_time) and the head of the next night
    (start_time -> 24:00). A window that does not cross midnight is a single
    range. (`start_time == end_time` is rejected by `tariffs` validation, so
    it is not handled here.)
    """
    tzinfo = segment.start.tzinfo
    day_start = datetime.combine(segment.day, time.min, tzinfo=tzinfo)
    day_end = day_start + timedelta(days=1)

    start_dt = day_start + _time_offset(nightly.start_time)
    end_dt = day_start + _time_offset(nightly.end_time)

    if start_dt < end_dt:
        return [(start_dt, end_dt)]
    return [(day_start, end_dt), (start_dt, day_end)]


def _time_offset(hhmm: str) -> timedelta:
    hours, minutes = (int(part) for part in hhmm.split(":"))
    return timedelta(hours=hours, minutes=minutes)


def _to_seconds(delta: timedelta) -> int:
    return round(delta.total_seconds())


def _ceil_hours(seconds: int) -> int:
    if seconds <= 0:
        return 0
    return (seconds + _SECONDS_PER_HOUR - 1) // _SECONDS_PER_HOUR


def _clamped_amount(amount: int) -> Decimal:
    # Defense in depth: `tariffs` validation already rejects amount <= 0 at
    # creation time; clamp again here so a raw/malformed Tariff can never
    # push a charge negative.
    return Decimal(max(amount, 0))
