"""Check-in endpoints."""

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.application.check_in_service import CheckInService
from app.domain.pagination import PageRequest
from app.domain.user import User
from app.presentation.deps import (
    get_check_in_service,
    get_current_user,
    get_upload_limits,
)
from app.presentation.idempotency import IdempotencyGuard, idempotency_guard
from app.presentation.pagination import page_request, with_total
from app.presentation.schemas import CheckInForm, CheckInRead
from app.presentation.uploads import UploadLimits, read_photo_uploads

router = APIRouter(tags=["check-ins"])


@router.get(
    "/check-ins",
    response_model=list[CheckInRead],
    dependencies=[Depends(get_current_user)],
)
async def list_check_ins(
    response: Response,
    page: PageRequest = Depends(page_request),
    service: CheckInService = Depends(get_check_in_service),
) -> list[CheckInRead]:
    result = await service.list_open(page)
    return [CheckInRead.from_view(view) for view in with_total(response, result)]


@router.post(
    "/check-ins",
    response_model=CheckInRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_check_in(
    form: CheckInForm = Depends(CheckInForm.as_form),
    photos: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    limits: UploadLimits = Depends(get_upload_limits),
    guard: IdempotencyGuard = Depends(idempotency_guard),
    service: CheckInService = Depends(get_check_in_service),
) -> CheckInRead | Response:
    if (replay := await guard.replay()) is not None:
        return replay
    command = form.to_command(user.id, await read_photo_uploads(photos, limits))
    result = CheckInRead.from_view(await service.create_check_in(command))
    await guard.remember(status.HTTP_201_CREATED, result)
    return result
