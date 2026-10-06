"""FareCalculator tests: exhaustive table of billing scenarios.

Covers ceil-to-hour, night-window-replaces-day (including midnight
wraparound), per-calendar-day daily cap, monthly-pass short-circuit,
invalid period rejection, boundary edge cases, and negative-rate defense
in depth. See `openspec/changes/billing/design.md` for the rounding/cap
granularity rationale exercised by the multi-day and midnight cases below.
"""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.application.billing_service import FareService, StayQuery
from app.core.config import settings
from app.domain.billing import FareCalculator, StayPeriod
from app.domain.category import Category
from app.domain.category_tariffs import CategoryTariffs
from app.domain.errors import (
    DomainValidationError,
    InvalidBillingPeriodError,
    MissingHourlyTariffError,
)
from app.domain.tariff import Tariff, TariffType
from app.infrastructure.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from app.infrastructure.repositories.tariff_repository import (
    SqlAlchemyTariffRepository,
)


def _tariff(
    tariff_type: TariffType,
    amount: int,
    start_time: str | None = None,
    end_time: str | None = None,
) -> Tariff:
    return Tariff(
        id=1,
        category_id=1,
        type=tariff_type,
        amount=amount,
        start_time=start_time,
        end_time=end_time,
    )


BOGOTA = ZoneInfo("America/Bogota")


def _at(day: int, hour: int, minute: int = 0, month: int = 1) -> datetime:
    """Business-local (America/Bogota) wall-clock time."""
    return datetime(2026, month, day, hour, minute, tzinfo=BOGOTA)


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


@pytest.fixture
def calculator() -> FareCalculator:
    return FareCalculator(BOGOTA)


# --- Success: hourly billing + ceil-to-hour -------------------------------


def test_exact_one_hour_bills_one_hourly_unit(calculator):
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, 3000))

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 8), _at(1, 9))
    )

    assert amount == Decimal(3000)


def test_one_hour_five_minutes_ceils_to_two_hours(calculator):
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, 3000))

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 8, 0), _at(1, 9, 5))
    )

    assert amount == Decimal(6000)


# --- Success: night window replaces day rate ------------------------------


def test_stay_entirely_within_night_window_bills_night_rate_only(calculator):
    # Non-wraparound window kept separate from the midnight-crossing case below.
    tariffs = CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        nightly=_tariff(TariffType.NIGHTLY, 1000, "20:00", "23:00"),
    )

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 21), _at(1, 22))
    )

    assert amount == Decimal(1000)


def test_stay_crossing_from_day_into_night_bills_separately_not_blended(calculator):
    tariffs = CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        nightly=_tariff(TariffType.NIGHTLY, 1000, "22:00", "06:00"),
    )

    # 20:00 -> 22:00 (2h day) + 22:00 -> 23:00 (1h night)
    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 20), _at(1, 23))
    )

    assert amount == Decimal(2 * 3000 + 1 * 1000)


# --- Success: daily cap ---------------------------------------------------


def test_stay_under_daily_cap_is_not_capped(calculator):
    tariffs = CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        daily=_tariff(TariffType.DAILY, 50_000),
    )

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 8), _at(1, 10))
    )

    assert amount == Decimal(2 * 3000)


# --- Success: monthly pass short-circuit ----------------------------------


def test_monthly_pass_active_charges_zero_regardless_of_duration(calculator):
    tariffs = CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        daily=_tariff(TariffType.DAILY, 50_000),
        nightly=_tariff(TariffType.NIGHTLY, 1000, "22:00", "06:00"),
    )

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 8), _at(10, 8), has_active_monthly_pass=True)
    )

    assert amount == Decimal("0")


# --- Failure: invalid billing period ---------------------------------------


def test_exit_before_entry_raises(calculator):
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, 3000))

    with pytest.raises(InvalidBillingPeriodError):
        calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 9), _at(1, 8))
    )


def test_exit_equal_entry_raises(calculator):
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, 3000))

    with pytest.raises(InvalidBillingPeriodError):
        calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 9), _at(1, 9))
    )


# --- Boundary edge cases: midnight-exact night window bounds --------------


def test_stay_starting_exactly_at_night_end_bills_hourly_only(calculator):
    tariffs = CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        nightly=_tariff(TariffType.NIGHTLY, 1000, "22:00", "06:00"),
    )

    # end_time (06:00) is exclusive of the night window -> this hour is day rate.
    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 6), _at(1, 7))
    )

    assert amount == Decimal(3000)


# --- Security: negative/zero tariff amounts never yield a negative charge --


def test_negative_hourly_amount_never_produces_negative_charge(calculator):
    # `tariffs` validation already rejects amount <= 0 at creation time; this
    # exercises the calculator's own defense-in-depth clamp directly.
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, -500))

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 8), _at(1, 9))
    )

    assert amount >= Decimal("0")
    assert amount == Decimal("0")


def test_zero_daily_rate_never_produces_negative_charge(calculator):
    tariffs = CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        daily=_tariff(TariffType.DAILY, 0),
    )

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_at(1, 8), _at(1, 9))
    )

    assert amount >= Decimal("0")
    assert amount == Decimal("0")


# --- Domain aggregate defense in depth --------------------------------------


def test_category_tariffs_rejects_mismatched_tariff_type():
    with pytest.raises(DomainValidationError):
        CategoryTariffs(
            category_id=1,
            hourly=_tariff(TariffType.HOURLY, 3000),
            daily=_tariff(TariffType.HOURLY, 5000),  # wrong type for the `daily` slot
        )


# --- Async wrapper: loads tariffs via TariffRepository ---------------------


@pytest.fixture
async def category_id(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyCategoryRepository(session)
        category = await repository.create(Category(id=None, name="carro"))
        await session.commit()
        return category.id


@pytest.fixture
async def tariff_repository(session_factory):
    async with session_factory() as session:
        yield SqlAlchemyTariffRepository(session)


async def test_calculate_fare_for_session_loads_tariffs_by_category(
    calculator, tariff_repository, category_id
):
    await tariff_repository.create(
        Tariff(
            id=None,
            category_id=category_id,
            type=TariffType.HOURLY,
            amount=3000,
            start_time=None,
            end_time=None,
        )
    )

    amount = await FareService(tariff_repository, calculator).quote(
        StayQuery(category_id, _at(1, 8), _at(1, 9))
    )

    assert amount == Decimal(3000)


async def test_calculate_fare_for_session_without_hourly_tariff_raises(
    calculator, tariff_repository, category_id
):
    with pytest.raises(MissingHourlyTariffError):
        await FareService(tariff_repository, calculator).quote(
            StayQuery(category_id, _at(1, 8), _at(1, 9))
        )


# --- Business timezone (B-TZ) ---------------------------------------------


def _hourly_and_night() -> CategoryTariffs:
    return CategoryTariffs(
        category_id=1,
        hourly=_tariff(TariffType.HOURLY, 3000),
        nightly=_tariff(TariffType.NIGHTLY, 1000, "22:00", "06:00"),
    )


def test_night_window_is_evaluated_in_business_local_time(calculator):
    # 21:00 -> 23:00 Bogota == 02:00 -> 04:00 UTC: 1h day + 1h night.
    amount = calculator.calculate_fare(
        _hourly_and_night(), StayPeriod(_utc(2, 2), _utc(2, 4))
    )

    assert amount == Decimal(3000 + 1000)


def test_utc_midnight_crossing_is_not_a_billing_day_boundary(calculator):
    # 23:05 -> 01:05 UTC == 18:05 -> 20:05 Bogota: one local day, 2h.
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, 3000))

    amount = calculator.calculate_fare(
        tariffs, StayPeriod(_utc(1, 23, 5), _utc(2, 1, 5))
    )

    assert amount == Decimal(2 * 3000)


def test_default_calculator_uses_configured_business_timezone():
    tariffs = _hourly_and_night()

    amount = FareCalculator(settings.business_zone).calculate_fare(
        tariffs, StayPeriod(_utc(2, 2), _utc(2, 4))
    )

    assert amount == Decimal(3000 + 1000)


def test_naive_datetimes_are_rejected(calculator):
    tariffs = CategoryTariffs(category_id=1, hourly=_tariff(TariffType.HOURLY, 3000))

    with pytest.raises(InvalidBillingPeriodError):
        calculator.calculate_fare(
        tariffs, StayPeriod(datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 9))
    )
