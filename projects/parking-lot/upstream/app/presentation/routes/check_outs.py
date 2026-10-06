"""Check-out endpoints."""

from fastapi import APIRouter, Depends, Response, status

from app.application.check_out_service import CheckOutService
from app.application.commands import CheckOutCommand
from app.presentation.deps import get_check_out_service, get_current_user
from app.presentation.idempotency import IdempotencyGuard, idempotency_guard
from app.presentation.schemas import CheckOutRead, CheckOutRequest

router = APIRouter(tags=["check-outs"])


@router.post(
    "/check-outs/{session_id}",
    response_model=CheckOutRead,
    dependencies=[Depends(get_current_user)],
)
async def create_check_out(
    session_id: int,
    body: CheckOutRequest | None = None,
    guard: IdempotencyGuard = Depends(idempotency_guard),
    service: CheckOutService = Depends(get_check_out_service),
) -> CheckOutRead | Response:
    if (replay := await guard.replay()) is not None:
        return replay
    command = CheckOutCommand(session_id, body.client_exit_time if body else None)
    result = CheckOutRead.from_closed(await service.close_session(command))
    await guard.remember(status.HTTP_200_OK, result)
    return result
