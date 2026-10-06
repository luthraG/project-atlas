"""LIMIT/OFFSET + COUNT(*) helper shared by SQLAlchemy repositories."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pagination import PageRequest


@dataclass(frozen=True)
class PagedQuery:
    statement: Select  # ordered SELECT of one ORM entity
    page: PageRequest


async def fetch_page(session: AsyncSession, query: PagedQuery) -> tuple[list[Any], int]:
    """Return (models of the requested window, total matching rows)."""
    counted = select(func.count()).select_from(query.statement.order_by(None).subquery())
    total = await session.scalar(counted)
    window = query.statement.limit(query.page.limit).offset(query.page.offset)
    models = list((await session.execute(window)).scalars())
    return models, int(total or 0)
