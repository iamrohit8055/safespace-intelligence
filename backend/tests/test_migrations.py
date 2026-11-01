"""Tests for database migrations and extension management."""

import importlib.util
import inspect
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import SessionLocal

_migration_path = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0001_enable_postgis.py"
)
_spec = importlib.util.spec_from_file_location("migration_0001", _migration_path)
migration_0001 = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(migration_0001)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a real database session for integration testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_postgis_migration_metadata() -> None:
    """Verify metadata definitions of initial PostGIS migration."""
    assert migration_0001.revision == "0001_enable_postgis"
    assert migration_0001.down_revision is None


def test_postgis_migration_downgrade_preserves_extension() -> None:
    """Verify downgrade function does not execute DROP EXTENSION to preserve PostGIS."""
    source = inspect.getsource(migration_0001.downgrade)
    assert "DROP EXTENSION" not in source
    # Downgrade executes safely without exception
    migration_0001.downgrade()


def test_postgis_extension_is_active(db_session: Session) -> None:
    """Verify that PostGIS extension is installed and responds to version query."""
    result = db_session.execute(text("SELECT PostGIS_Version();")).scalar()
    assert result is not None
    assert "3.5" in result
