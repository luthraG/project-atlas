"""Monthly pass endpoints."""

from fastapi import APIRouter, Depends, Response, status

from app.application.monthly_pass_service import MonthlyPassPatch, MonthlyPassService
from app.domain.monthly_pass import MonthlyPass
from app.domain.pagination import PageRequest
from app.presentation.deps import get_current_user, get_monthly_pass_service, require_admin
from app.presentation.pagination import page_request, with_total
from app.presentation.schemas import MonthlyPassCreate, MonthlyPassRead, MonthlyPassUpdate

router = APIRouter(tags=["monthly-passes"])


@router.get(
    "/monthly-passes",
    response_model=list[MonthlyPassRead],
    dependencies=[Depends(get_current_user)],
)
async def list_monthly_passes(
    response: Response,
    vehicle_id: int | None = None,
    page: PageRequest = Depends(page_request),
    service: MonthlyPassService = Depends(get_monthly_pass_service),
) -> list[MonthlyPassRead]:
    result = await service.list_page(page, vehicle_id)
    return [MonthlyPassRead.model_validate(item) for item in with_total(response, result)]


@router.post(
    "/monthly-passes",
    response_model=MonthlyPassRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_monthly_pass(
    body: MonthlyPassCreate, service: MonthlyPassService = Depends(get_monthly_pass_service)
) -> MonthlyPassRead:
    monthly_pass = MonthlyPass(id=None, **body.model_dump())
    return MonthlyPassRead.model_validate(await service.create(monthly_pass))


@router.patch(
    "/monthly-passes/{pass_id}",
    response_model=MonthlyPassRead,
    dependencies=[Depends(require_admin)],
)
async def update_monthly_pass(
    pass_id: int,
    body: MonthlyPassUpdate,
    service: MonthlyPassService = Depends(get_monthly_pass_service),
) -> MonthlyPassRead:
    patch = MonthlyPassPatch(**body.model_dump())
    return MonthlyPassRead.model_validate(await service.update(pass_id, patch))


@router.delete(
    "/monthly-passes/{pass_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_monthly_pass(
    pass_id: int, service: MonthlyPassService = Depends(get_monthly_pass_service)
) -> None:
    await service.delete(pass_id)
