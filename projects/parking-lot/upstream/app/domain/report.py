"""Domain shapes for revenue and occupancy reports (read-only aggregation)."""

from dataclasses import dataclass, field


@dataclass
class DailyRevenue:
    date: str
    amount: int


@dataclass
class CategoryRevenue:
    category_id: int
    category_name: str
    amount: int


@dataclass
class RevenueReport:
    total: int
    by_day: list[DailyRevenue] = field(default_factory=list)
    by_category: list[CategoryRevenue] = field(default_factory=list)


@dataclass
class CategoryOccupancy:
    category_id: int
    category_name: str
    count: int


@dataclass
class OccupancyReport:
    total_open: int
    by_category: list[CategoryOccupancy] = field(default_factory=list)
