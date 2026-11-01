"""Health check route definitions."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import check_database_connection, get_db

logger = logging.getLogger("safespace.health")
settings = get_settings()

# Root health router (GET /health)
health_router = APIRouter()

# API v1 health router (GET /api/v1/health and GET /api/v1/health/database)
api_v1_health_router = APIRouter()


@health_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Root Service Health Check",
    description="Returns high-level status of the application.",
)
def root_health_check() -> dict[str, Any]:
    """Root application health check."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@api_v1_health_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="API v1 Health Check",
    description="Returns API v1 status and operational metadata.",
)
def api_v1_health_check() -> dict[str, Any]:
    """API v1 status check."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_version": "v1",
    }


@api_v1_health_router.get(
    "/database",
    status_code=status.HTTP_200_OK,
    summary="Database Connectivity Health Check",
    description="Executes a lightweight query (SELECT 1) to verify database connectivity.",
    responses={
        200: {
            "description": "Database is reachable and responding normally.",
            "content": {
                "application/json": {"example": {"status": "healthy", "database": "reachable"}}
            },
        },
        503: {
            "description": "Database is unavailable or unreachable.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "database": "unreachable",
                        "detail": "Database service is unavailable",
                    }
                }
            },
        },
    },
)
def database_health_check(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    """Verify database connection with a lightweight query without leaking credentials on error."""
    try:
        check_database_connection(db)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "database": "reachable",
            },
        )
    except SQLAlchemyError as exc:
        logger.error("Database health check failed: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "unreachable",
                "detail": "Database service is unavailable",
            },
        )
    except Exception as exc:
        logger.error("Unexpected error during database health check: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "unreachable",
                "detail": "Database service is unavailable",
            },
        )
