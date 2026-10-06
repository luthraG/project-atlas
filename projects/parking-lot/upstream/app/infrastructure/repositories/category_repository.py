"""SQLAlchemy implementation of the category repository port."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.category import Category
from app.domain.repositories import CategoryRepository
from app.infrastructure.models import CategoryModel


class SqlAlchemyCategoryRepository(CategoryRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_entity(model: CategoryModel) -> Category:
        return Category(id=model.id, name=model.name)

    async def get_by_name(self, name: str) -> Category | None:
        result = await self._session.execute(
            select(CategoryModel).where(CategoryModel.name == name)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, category_id: int) -> Category | None:
        model = await self._session.get(CategoryModel, category_id)
        return self._to_entity(model) if model else None

    async def list_all(self) -> list[Category]:
        result = await self._session.execute(
            select(CategoryModel).order_by(CategoryModel.name)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def create(self, category: Category) -> Category:
        model = CategoryModel(name=category.name)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, category: Category) -> Category:
        model = await self._session.get(CategoryModel, category.id)
        model.name = category.name
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, category_id: int) -> None:
        model = await self._session.get(CategoryModel, category_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
