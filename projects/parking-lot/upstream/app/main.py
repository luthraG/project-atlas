"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.infrastructure.local_evidence_storage import ensure_storage_root
from app.infrastructure.shared_resources import build_shared_resources
from app.presentation.deps import install_shared_resources
from app.presentation.errors import register_exception_handlers
from app.presentation.request_log import RequestLogMiddleware
from app.presentation.routes import (
    auth,
    billing,
    categories,
    check_ins,
    check_outs,
    health,
    monthly_passes,
    reports,
    tariffs,
    users,
    vehicles,
)

# Startup notices go to the server log channel (configured by uvicorn).
logger = logging.getLogger("uvicorn.error")

_ROUTERS = (health, auth, users, categories, tariffs, vehicles, check_ins, check_outs,
            billing, monthly_passes, reports)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_storage_root(settings.evidence_storage_path)
    resources = build_shared_resources(settings.redis_url)
    previous = install_shared_resources(resources)
    logger.info("Shared cache/login limiter backend: %s", resources.backend)
    try:
        yield
    finally:
        install_shared_resources(previous)
        await resources.aclose()


def create_app() -> FastAPI:
    configure_logging(settings.log_format, settings.log_file)
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    # Catch-all first (innermost) so CORS still decorates generic 500s.
    register_exception_handlers(application)
    # Auth is a Bearer header (no cookies): credentials are never needed.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-None-Match"],
        expose_headers=["X-Total-Count", "ETag", "Retry-After", "Idempotent-Replayed"],
    )
    application.add_middleware(RequestLogMiddleware)
    for module in _ROUTERS:
        application.include_router(module.router, prefix=settings.api_prefix)
    return application


app = create_app()
