"""Pytest fixtures and configuration for SafeSpace Intelligence tests."""

import os
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

# Set testing environment before loading application settings
os.environ["APP_ENV"] = "testing"
os.environ["DEBUG"] = "true"

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Ensure cached settings are clean for test execution."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client fixture for HTTP requests."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Mock database session that simulates successful query execution."""
    session = MagicMock()
    session.execute.return_value = MagicMock()
    return session


@pytest.fixture
def mock_failing_db_session() -> MagicMock:
    """Mock database session that simulates database outage/operational error."""
    session = MagicMock()
    session.execute.side_effect = OperationalError(
        statement="SELECT 1;",
        params={},
        orig=Exception("Connection refused: database server down"),
    )
    return session
