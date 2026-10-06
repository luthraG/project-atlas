"""SQLAlchemy implementation of the idempotency store port."""

from datetime import UTC, datetime

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import IdempotencyKeyInUseError
from app.domain.ports import IdempotencyRecord, IdempotencyStore
from app.infrastructure.models import IdempotencyKeyModel


def _aware(value: datetime) -> datetime:
    # SQLite drops tzinfo; every timestamp here is written in UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class SqlAlchemyIdempotencyStore(IdempotencyStore):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, key: str) -> IdempotencyRecord | None:
        model = await self._session.get(IdempotencyKeyModel, key)
        if model is None:
            return None
        return IdempotencyRecord(
            key=model.key, user_id=model.user_id, endpoint=model.endpoint,
            status_code=model.status_code, response_body=model.response_body,
            created_at=_aware(model.created_at),
        )

    async def reserve(self, record: IdempotencyRecord) -> None:
        model = IdempotencyKeyModel(
            key=record.key, user_id=record.user_id, endpoint=record.endpoint,
            status_code=record.status_code, response_body=record.response_body,
            created_at=record.created_at,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(model)
        except IntegrityError as exc:  # concurrent request with the same key won
            raise IdempotencyKeyInUseError() from exc

    async def complete(self, record: IdempotencyRecord) -> None:
        await self._session.execute(
            update(IdempotencyKeyModel)
            .where(IdempotencyKeyModel.key == record.key)
            .values(status_code=record.status_code, response_body=record.response_body)
        )

    async def purge_older_than(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(IdempotencyKeyModel).where(IdempotencyKeyModel.created_at < cutoff)
        )
        return result.rowcount or 0
