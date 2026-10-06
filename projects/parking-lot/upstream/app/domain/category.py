"""Vehicle category domain entity and validation."""

from dataclasses import dataclass

from app.domain.errors import DomainValidationError


@dataclass
class Category:
    id: int | None
    name: str


def validate_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise DomainValidationError("Category name must not be empty")
    return value
