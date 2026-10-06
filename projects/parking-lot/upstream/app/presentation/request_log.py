"""Access log: one record per request with its route template, status and latency."""

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

logger = logging.getLogger("app.access")


def route_of(scope: Scope) -> str:
    """The matched route template (``/api/check-outs/{session_id}``), else the raw path."""
    route = getattr(scope.get("route"), "path", None)
    if route is None:
        return scope["path"]
    # Routers are included under the API prefix; the matched route keeps its own path.
    prefix = settings.api_prefix if scope["path"].startswith(settings.api_prefix) else ""
    return prefix + route


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def tracking_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        finally:
            logger.info(
                "request completed",
                extra={
                    "method": scope["method"],
                    "route": route_of(scope),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
