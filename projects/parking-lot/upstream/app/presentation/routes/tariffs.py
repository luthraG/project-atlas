"""Tariff endpoints."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.application.tariff_service import TariffPatch, TariffService
from app.domain.pagination import PageRequest
from app.domain.tariff import Tariff
from app.presentation.deps import get_current_user, get_tariff_service, require_admin
from app.presentation.http_cache import conditional_json
from app.presentation.pagination import TOTAL_COUNT_HEADER, page_request
from app.presentation.schemas import TariffCreate, TariffRead, TariffUpdate

router = APIRouter(tags=["tariffs"])


@router.get(
    "/tariffs",
    response_model=list[TariffRead],
    dependencies=[Depends(get_current_user)],
)
async def list_tariffs(
    request: Request,
    category_id: int | None = None,
    page: PageRequest = Depends(page_request),
    service: TariffService = Depends(get_tariff_service),
) -> Response:
    result = await service.list_page(page, category_id)
    items = [TariffRead.model_validate(tariff) for tariff in result.items]
    return conditional_json(request, items, {TOTAL_COUNT_HEADER: str(result.total)})


@router.post(
    "/tariffs",
    response_model=TariffRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_tariff(
    body: TariffCreate, service: TariffService = Depends(get_tariff_service)
) -> TariffRead:
    tariff = Tariff(id=None, category_id=body.category_id, type=body.type, amount=body.amount,
                    start_time=body.start_time, end_time=body.end_time)
    return TariffRead.model_validate(await service.create(tariff))


@router.patch(
    "/tariffs/{tariff_id}",
    response_model=TariffRead,
    dependencies=[Depends(require_admin)],
)
async def update_tariff(
    tariff_id: int,
    body: TariffUpdate,
    service: TariffService = Depends(get_tariff_service),
) -> TariffRead:
    patch = TariffPatch(**body.model_dump())
    return TariffRead.model_validate(await service.update(tariff_id, patch))


@router.delete(
    "/tariffs/{tariff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_tariff(
    tariff_id: int, service: TariffService = Depends(get_tariff_service)
) -> None:
    await service.delete(tariff_id)
