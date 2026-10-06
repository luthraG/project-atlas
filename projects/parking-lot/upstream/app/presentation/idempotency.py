"""``Idempotency-Key`` support for retry-prone writes (offline outbox).

Usage in a route::

    if (replay := await guard.replay()) is not None:
        return replay
    ...do the work...
    await guard.remember(201, dto)
"""

import json
from dataclasses import dataclass

from fastapi import Depends, Header, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.application.commands import IdempotentRequest, StoredResponse
from app.application.idempotency_service import IdempotencyService
from app.domain.user import User
from app.presentation.deps import get_current_user, get_idempotency_service

REPLAYED_HEADER = "Idempotent-Replayed"
MAX_KEY_LENGTH = 100


@dataclass
class IdempotencyGuard:
    service: IdempotencyService
    request: IdempotentRequest | None  # None: client sent no key

    async def replay(self) -> Response | None:
        if self.request is None:
            return None
        stored = await self.service.begin(self.request)
        if stored is None:
            return None
        return Response(stored.body, status_code=stored.status_code,
                        media_type="application/json", headers={REPLAYED_HEADER: "true"})

    async def remember(self, status_code: int, payload: BaseModel) -> None:
        if self.request is None:
            return
        body = json.dumps(jsonable_encoder(payload))
        await self.service.complete(self.request, StoredResponse(status_code, body))


async def idempotency_guard(
    request: Request,
    key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1,
                             max_length=MAX_KEY_LENGTH),
    user: User = Depends(get_current_user),
    service: IdempotencyService = Depends(get_idempotency_service),
) -> IdempotencyGuard:
    if key is None:
        return IdempotencyGuard(service, None)
    endpoint = f"{request.method} {request.url.path}"
    return IdempotencyGuard(service, IdempotentRequest(key, user.id, endpoint))
