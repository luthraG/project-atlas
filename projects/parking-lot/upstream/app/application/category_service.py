"""Vehicle category use cases."""

from app.domain.category import Category, validate_name
from app.domain.errors import CategoryNotFoundError, DuplicateCategoryNameError
from app.domain.pagination import Page, PageRequest, paginate
from app.domain.repositories import CategoryRepository

__all__ = ["CategoryNotFoundError", "CategoryService", "DuplicateCategoryNameError"]


class CategoryService:
    def __init__(self, categories: CategoryRepository):
        self._categories = categories

    async def create(self, name: str) -> Category:
        value = validate_name(name)
        if await self._categories.get_by_name(value) is not None:
            raise DuplicateCategoryNameError()
        return await self._categories.create(Category(id=None, name=value))

    async def list_page(self, page: PageRequest) -> Page[Category]:
        # Small, cached catalog: slice in memory.
        return paginate(await self._categories.list_all(), page)

    async def update(self, category_id: int, name: str) -> Category:
        value = validate_name(name)
        category = await self._categories.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundError()
        existing = await self._categories.get_by_name(value)
        if existing is not None and existing.id != category_id:
            raise DuplicateCategoryNameError()
        category.name = value
        return await self._categories.update(category)

    async def delete(self, category_id: int) -> None:
        if await self._categories.get_by_id(category_id) is None:
            raise CategoryNotFoundError()
        await self._categories.delete(category_id)
