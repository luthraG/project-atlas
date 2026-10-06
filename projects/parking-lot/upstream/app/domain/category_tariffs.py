"""Aggregate bundling a category's tariff rows for fare calculation.

`Tariff` models exactly one rate row (one `category_id` + one `TariffType`
per row), matching how the `tariffs` capability stores and validates them.
Billing needs the hourly, (optional) daily, and (optional) nightly rows for
a single category together, so this small aggregate bundles them rather than
reshaping `Tariff` itself.
"""

from dataclasses import dataclass

from app.domain.errors import DomainValidationError
from app.domain.tariff import Tariff, TariffType


@dataclass
class CategoryTariffs:
    category_id: int
    hourly: Tariff
    daily: Tariff | None = None
    nightly: Tariff | None = None

    def __post_init__(self) -> None:
        _assert_type(self.hourly, TariffType.HOURLY)
        _assert_type(self.daily, TariffType.DAILY)
        _assert_type(self.nightly, TariffType.NIGHTLY)
        if self.nightly is not None and (
            self.nightly.start_time is None or self.nightly.end_time is None
        ):
            raise DomainValidationError("Nightly tariff requires a time window")


def _assert_type(tariff: Tariff | None, expected: TariffType) -> None:
    if tariff is not None and tariff.type != expected:
        raise DomainValidationError(f"Expected a {expected.value} tariff, got {tariff.type.value}")
