"""Main FastAPI application entrypoint for SafeSpace Intelligence."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.health.routes import health_router

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("safespace.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown routines."""
    logger.info(
        "Starting %s [version: %s, env: %s, debug: %s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
        settings.DEBUG,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Application factory for configuring and assembling the FastAPI app."""
    # Swagger / OpenAPI documentation is enabled in development/testing or when DEBUG is True
    enable_docs = settings.DEBUG or not settings.is_production
    docs_url = "/docs" if enable_docs else None
    redoc_url = "/redoc" if enable_docs else None
    openapi_url = "/openapi.json" if enable_docs else None

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "SafeSpace Intelligence backend: Location-based public-space "
            "infrastructure auditing, safety deficiency analysis, and recommendations."
        ),
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # Configure CORS
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Register root health check (GET /health)
    app.include_router(health_router, tags=["Health"])

    # Register API v1 router (includes /health, /database, and future endpoints)
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
