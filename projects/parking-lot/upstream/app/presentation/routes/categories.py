"""Vehicle category endpoints."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.application.category_service import CategoryService
from app.domain.pagination import PageRequest
from app.presentation.deps import get_category_service, get_current_user, require_admin
from app.presentation.http_cache import conditional_json
from app.presentation.pagination import TOTAL_COUNT_HEADER, page_request
from app.presentation.schemas import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(tags=["categories"])


@router.get(
    "/categories",
    response_model=list[CategoryRead],
    dependencies=[Depends(get_current_user)],
)
async def list_categories(
    request: Request,
    page: PageRequest = Depends(page_request),
    service: CategoryService = Depends(get_category_service),
) -> Response:
    result = await service.list_page(page)
    items = [CategoryRead.model_validate(category) for category in result.items]
    return conditional_json(request, items, {TOTAL_COUNT_HEADER: str(result.total)})


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_category(
    body: CategoryCreate, service: CategoryService = Depends(get_category_service)
) -> CategoryRead:
    return CategoryRead.model_validate(await service.create(body.name))


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryRead,
    dependencies=[Depends(require_admin)],
)
async def update_category(
    category_id: int,
    body: CategoryUpdate,
    service: CategoryService = Depends(get_category_service),
) -> CategoryRead:
    return CategoryRead.model_validate(await service.update(category_id, body.name))


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_category(
    category_id: int, service: CategoryService = Depends(get_category_service)
) -> None:
    await service.delete(category_id)
