"""Async SQLAlchemy engine, session factory, and request unit of work."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import DataError, DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.domain.errors import DomainValidationError

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _is_data_error(exc: DBAPIError) -> bool:
    # asyncpg surfaces SQLSTATE class 22 ("data exception", e.g. 22001
    # string_data_right_truncation) as a plain DBAPIError.
    sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc, "pgcode", None)
    return isinstance(exc, DataError) or str(sqlstate or "").startswith("22")


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One transaction per request: commit on success, rollback on error.

    Database-level data errors (e.g. value too long for VARCHAR(n) on
    Postgres) become a 422 domain error instead of an opaque 500.
    """
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except DBAPIError as exc:
            await session.rollback()
            if _is_data_error(exc):
                raise DomainValidationError(
                    "Invalid data: a value is too long or malformed"
                ) from exc
            raise
        except BaseException:
            await session.rollback()
            raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_scope(async_session_factory) as session:
        yield session
