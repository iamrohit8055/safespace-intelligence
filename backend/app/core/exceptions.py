"""Centralized application exceptions and error handling."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("safespace.exceptions")


class AppException(Exception):
    """Base exception for application-level operational errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class DatabaseConnectionError(AppException):
    """Raised when the database connection fails or is unreachable."""

    def __init__(
        self,
        message: str = "Database service is unavailable",
        details: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="DATABASE_UNAVAILABLE",
            details=details,
        )


class EntityNotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        entity_name: str,
        entity_id: Any,
    ) -> None:
        super().__init__(
            message=f"{entity_name} with id '{entity_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ENTITY_NOT_FOUND",
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": exc.error_code,
            "message": exc.message,
        },
    }
    if exc.details is not None:
        payload["error"]["details"] = exc.details

    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle schema validation errors cleanly."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": exc.errors(),
            },
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions without leaking stack traces or sensitive credentials."""
    logger.exception("Unhandled server error: %s", str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            },
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
