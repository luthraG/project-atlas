"""User management endpoints (admin only)."""

from fastapi import APIRouter, Depends, Response, status

from app.application.commands import CreateUserCommand, UserPatch
from app.application.user_service import UserService
from app.domain.pagination import PageRequest
from app.presentation.deps import get_user_service, require_admin
from app.presentation.pagination import page_request, with_total
from app.presentation.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(tags=["users"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserRead])
async def list_users(
    response: Response,
    page: PageRequest = Depends(page_request),
    service: UserService = Depends(get_user_service),
) -> list[UserRead]:
    result = await service.list_page(page)
    return [UserRead.model_validate(user) for user in with_total(response, result)]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate, service: UserService = Depends(get_user_service)
) -> UserRead:
    command = CreateUserCommand(body.username, body.display_name, body.role, body.pin)
    return UserRead.model_validate(await service.create(command))


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, body: UserUpdate, service: UserService = Depends(get_user_service)
) -> UserRead:
    patch = UserPatch(body.display_name, body.role, body.is_active)
    return UserRead.model_validate(await service.update(user_id, patch))
