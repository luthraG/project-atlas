"""User management use cases."""

from app.application.commands import CreateUserCommand, UserPatch
from app.domain.errors import DuplicateUsernameError, UserNotFoundError
from app.domain.pagination import Page, PageRequest
from app.domain.ports import PasswordHasher
from app.domain.repositories import UserRepository
from app.domain.user import User, validate_pin

__all__ = ["DuplicateUsernameError", "UserNotFoundError", "UserService"]


class UserService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher):
        self._users = users
        self._hasher = hasher

    async def create(self, command: CreateUserCommand) -> User:
        validate_pin(command.pin)
        if await self._users.get_by_username(command.username) is not None:
            raise DuplicateUsernameError()
        user = User(
            id=None,
            username=command.username,
            display_name=command.display_name,
            role=command.role,
            pin_hash=await self._hasher.hash(command.pin),
        )
        return await self._users.create(user)

    async def list_page(self, page: PageRequest) -> Page[User]:
        return await self._users.list_page(page)

    async def update(self, user_id: int, patch: UserPatch) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if patch.display_name is not None:
            user.display_name = patch.display_name
        if patch.role is not None:
            user.role = patch.role
        if patch.is_active is not None:
            user.is_active = patch.is_active
        return await self._users.update(user)
