"""Offset pagination value objects shared by repositories and services."""

from collections.abc import Sequence
from dataclasses import dataclass, field

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@dataclass(frozen=True)
class PageRequest:
    limit: int = DEFAULT_LIMIT
    offset: int = 0


@dataclass(frozen=True)
class Page[T]:
    items: list[T] = field(default_factory=list)
    total: int = 0


def paginate[T](items: Sequence[T], page: PageRequest) -> Page[T]:
    """In-memory slice for small, already-loaded collections."""
    window = list(items[page.offset : page.offset + page.limit])
    return Page(items=window, total=len(items))
