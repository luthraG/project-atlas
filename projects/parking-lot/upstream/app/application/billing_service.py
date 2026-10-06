"""Fare quote use case: load a category's tariffs and price a stay."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.billing import FareCalculator, StayPeriod, select_category_tariffs
from app.domain.category_tariffs import CategoryTariffs
from app.domain.repositories import TariffRepository

logger = logging.getLogger("app.billing")


@dataclass(frozen=True)
class StayQuery:
    """Parameter object: a category's stay to be priced."""

    category_id: int
    entry_time: datetime
    exit_time: datetime
    has_active_monthly_pass: bool = False

    @property
    def period(self) -> StayPeriod:
        return StayPeriod(self.entry_time, self.exit_time, self.has_active_monthly_pass)


class FareService:
    def __init__(self, tariffs: TariffRepository, calculator: FareCalculator):
        self._tariffs = tariffs
        self._calculator = calculator

    async def quote(self, query: StayQuery) -> Decimal:
        rows = await self._tariffs.list_by_category(query.category_id)
        tariffs = select_category_tariffs(query.category_id, rows)
        amount = self._calculator.calculate_fare(tariffs, query.period)
        self._check_daily_maximum(query, tariffs, amount)
        return amount

    def _check_daily_maximum(self, query: StayQuery, tariffs: CategoryTariffs, amount: Decimal) -> None:
        """A stay never costs more than the daily rate for each business day it touches."""
        if tariffs.daily is None:
            return
        first = self._calculator.local_date(query.entry_time)
        last = self._calculator.local_date(query.exit_time - timedelta(microseconds=1))
        days = (last - first).days + 1
        maximum = days * tariffs.daily.amount
        if amount > maximum:
            logger.error(
                "Fare exceeds the daily maximum",
                extra={"category_id": query.category_id, "amount": int(amount),
                       "maximum": maximum, "days": days},
            )
