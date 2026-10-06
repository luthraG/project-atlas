"""Idempotent replay of client writes keyed by ``Idempotency-Key``.

Protocol (inside the request's single transaction):
1. ``begin``: purge expired keys, replay a completed record for the same
   user+endpoint, else reserve the key (pending row).
2. ``complete``: store the response on the reserved key.
A failed request rolls back, releasing the reservation, so the client can
retry with the same key.
"""

from datetime import timedelta

from app.application.commands import IdempotentRequest, StoredResponse
from app.domain.clock import Clock, system_clock
from app.domain.errors import IdempotencyKeyInUseError, IdempotencyKeyMismatchError
from app.domain.ports import IdempotencyRecord, IdempotencyStore

RETENTION = timedelta(hours=48)


class IdempotencyService:
    def __init__(self, store: IdempotencyStore, clock: Clock = system_clock):
        self._store = store
        self._clock = clock

    async def begin(self, request: IdempotentRequest) -> StoredResponse | None:
        """Stored response to replay, or None after reserving the key."""
        await self._store.purge_older_than(self._clock() - RETENTION)
        existing = await self._store.get(request.key)
        if existing is not None:
            return _replay(existing, request)
        try:
            await self._store.reserve(self._record(request))
        except IdempotencyKeyInUseError:
            # A concurrent request with this key committed first.
            winner = await self._store.get(request.key)
            if winner is None:
                raise
            return _replay(winner, request)
        return None

    async def complete(self, request: IdempotentRequest, response: StoredResponse) -> None:
        record = self._record(request)
        await self._store.complete(
            IdempotencyRecord(record.key, record.user_id, record.endpoint, record.created_at,
                              response.status_code, response.body)
        )

    def _record(self, request: IdempotentRequest) -> IdempotencyRecord:
        return IdempotencyRecord(request.key, request.user_id, request.endpoint, self._clock())


def _replay(record: IdempotencyRecord, request: IdempotentRequest) -> StoredResponse:
    # Never reveal another user's stored response.
    if record.user_id != request.user_id or record.is_pending:
        raise IdempotencyKeyInUseError()
    if record.endpoint != request.endpoint:
        raise IdempotencyKeyMismatchError()
    return StoredResponse(record.status_code, record.response_body)
