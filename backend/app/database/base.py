"""SQLAlchemy declarative base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All future domain models will inherit from this base.
    """

    pass
