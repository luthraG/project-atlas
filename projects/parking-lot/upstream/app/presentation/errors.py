"""Global exception handlers: one error contract for the whole API.

Domain errors -> ``{"detail": <message>, "code": <ExceptionClassName>}`` with
the status declared on the error class. Anything unexpected -> generic 500
(logged with traceback server-side, never echoed to the client).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.domain.errors import DomainError, TooManyRequestsError
from app.presentation.request_log import route_of

logger = logging.getLogger("app.errors")

INTERNAL_ERROR_BODY = {"detail": "Internal server error", "code": "InternalError"}


def error_body(exc: DomainError) -> dict[str, str]:
    return {"detail": str(exc), "code": type(exc).__name__}


def _headers_for(exc: DomainError) -> dict[str, str] | None:
    if isinstance(exc, TooManyRequestsError):
        return {"Retry-After": str(exc.retry_after_seconds)}
    return None


async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(error_body(exc), status_code=exc.status_code, headers=_headers_for(exc))


class UnhandledErrorMiddleware:
    """Pure ASGI catch-all: log the traceback, answer a generic 500.

    Unlike an ``Exception`` handler (which Starlette re-raises to the server),
    this swallows the error after logging it once, and sits inside CORS so
    browsers can still read the 500.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope["method"], route_of(scope))
            if started:
                raise
            await JSONResponse(INTERNAL_ERROR_BODY, status_code=500)(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_middleware(UnhandledErrorMiddleware)
