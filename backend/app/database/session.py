"""Database engine configuration, session management, and connectivity verification."""

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger("safespace.database")
settings = get_settings()

# Determine serverless execution environment (e.g. Vercel Functions)
is_serverless = os.getenv("VERCEL") == "1" or settings.DATABASE_POOL_TYPE.lower() == "null"

# Synchronous SQLAlchemy 2.x engine
if is_serverless:
    # Serverless execution: use NullPool to prevent connection exhaustion across ephemeral instances
    engine = create_engine(
        str(settings.DATABASE_URL),
        poolclass=NullPool,
        echo=settings.DEBUG and settings.APP_ENV == "development",
    )
else:
    # Standard server execution: pooled connections with pre-ping validation
    engine = create_engine(
        str(settings.DATABASE_URL),
        pool_pre_ping=True,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
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
