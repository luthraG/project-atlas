"""Query-string pagination (limit/offset) and the X-Total-Count header."""

from fastapi import Query, Response

from app.domain.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page, PageRequest

TOTAL_COUNT_HEADER = "X-Total-Count"


def page_request(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Page size"),
    offset: int = Query(0, ge=0, description="Items to skip"),
) -> PageRequest:
    return PageRequest(limit=limit, offset=offset)


def with_total(response: Response, page: Page) -> list:
    """Expose the unpaginated total in a header; body stays a plain list."""
    response.headers[TOTAL_COUNT_HEADER] = str(page.total)
    return page.items
