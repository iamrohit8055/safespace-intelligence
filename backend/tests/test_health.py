"""Tests for application health and status endpoints."""

from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.database.session import get_db
from app.main import app


def test_app_startup() -> None:
    """Verify application initializes with expected metadata and configuration."""
    assert isinstance(app, FastAPI)
    assert app.title == "SafeSpace Intelligence"
    assert app.version == "0.1.0"
    # Verify required OpenAPI route paths exist in application
    openapi_schema = app.openapi()
    paths = openapi_schema["paths"].keys()
    assert "/health" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/health/database" in paths


def test_root_health_endpoint(client: TestClient) -> None:
    """Verify root GET /health endpoint returns 200 and expected health metadata."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    data: dict[str, Any] = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "SafeSpace Intelligence"
    assert data["version"] == "0.1.0"
    assert "environment" in data


def test_api_v1_health_endpoint(client: TestClient) -> None:
    """Verify GET /api/v1/health endpoint returns 200 and version information."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK

    data: dict[str, Any] = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "SafeSpace Intelligence"
    assert data["version"] == "0.1.0"
    assert data["api_version"] == "v1"


def test_database_health_endpoint_success(
    client: TestClient,
    mock_db_session: MagicMock,
) -> None:
    """Verify GET /api/v1/health/database returns 200 when database query succeeds."""
    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        response = client.get("/api/v1/health/database")
        assert response.status_code == status.HTTP_200_OK

        data: dict[str, Any] = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "reachable"
        mock_db_session.execute.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_database_health_endpoint_failure(
    client: TestClient,
    mock_failing_db_session: MagicMock,
) -> None:
    """Verify GET /api/v1/health/database returns 503 without leaking credentials on failure."""
    app.dependency_overrides[get_db] = lambda: mock_failing_db_session

    try:
        response = client.get("/api/v1/health/database")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        data: dict[str, Any] = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "unreachable"
        assert data["detail"] == "Database service is unavailable"

        # Security check: ensure no raw credentials, DSN strings, or internal traces are exposed
        response_text = response.text.lower()
        assert "password" not in response_text
        assert "postgresql://" not in response_text
        assert "psycopg" not in response_text
        assert "traceback" not in response_text
    finally:
        app.dependency_overrides.clear()
