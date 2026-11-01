"""Database engine configuration, session management, and connectivity verification."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("safespace.database")
settings = get_settings()

# Synchronous SQLAlchemy 2.x engine
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=settings.DEBUG and settings.APP_ENV == "development",
)

# Central sessionmaker factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and guarantees closure upon request completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection(db: Session) -> bool:
    """Execute a lightweight query to verify active database connectivity.

    Returns:
        bool: True if query succeeds.

    Raises:
        SQLAlchemyError: If the database is unreachable or query execution fails.
    """
    try:
        db.execute(text("SELECT 1;"))
        return True
    except SQLAlchemyError as exc:
        logger.error("Database connectivity check failed: %s", exc.__class__.__name__)
        raise
