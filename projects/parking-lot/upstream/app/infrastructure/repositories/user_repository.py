"""SQLAlchemy implementation of the user repository port."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pagination import Page, PageRequest
from app.domain.repositories import UserRepository
from app.domain.user import User, UserRole
from app.infrastructure.models import UserModel
from app.infrastructure.repositories.paging import PagedQuery, fetch_page

_BY_ID = select(UserModel).order_by(UserModel.id)

class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            display_name=model.display_name,
            role=UserRole(model.role),
            pin_hash=model.pin_hash,
            is_active=model.is_active,
        )

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, user_id: int) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def list_all(self) -> list[User]:
        result = await self._session.execute(select(UserModel).order_by(UserModel.id))
        return [self._to_entity(model) for model in result.scalars()]

    async def list_page(self, page: PageRequest) -> Page[User]:
        models, total = await fetch_page(self._session, PagedQuery(_BY_ID, page))
        return Page([self._to_entity(model) for model in models], total)

    async def create(self, user: User) -> User:
        model = UserModel(
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            pin_hash=user.pin_hash,
            is_active=user.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        model.display_name = user.display_name
        model.role = user.role.value
        model.is_active = user.is_active
        await self._session.flush()
        return self._to_entity(model)
