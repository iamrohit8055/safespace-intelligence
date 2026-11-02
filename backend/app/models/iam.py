"""Identity and Access Management (IAM) SQLAlchemy models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.reporting import Report
    from app.models.verification import ReportVerification


class Role(Base):
    """System persona defining authorization privileges."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_roles",
        primaryjoin="Role.id == foreign(UserRole.role_id)",
        secondaryjoin="User.id == foreign(UserRole.user_id)",
        back_populates="roles",
        viewonly=True,
    )


class User(Base):
    """Registered citizen and personnel account."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="chk_users_email_format",
        ),
        Index("idx_users_email_lower", func.lower(text("email")), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=expression.false(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        foreign_keys="UserRole.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        primaryjoin="User.id == foreign(UserRole.user_id)",
        secondaryjoin="Role.id == foreign(UserRole.role_id)",
        back_populates="users",
        viewonly=True,
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="reporter",
    )
    verifications: Mapped[list["ReportVerification"]] = relationship(
        "ReportVerification",
        back_populates="verifier",
    )


class UserRole(Base):
    """Many-to-Many junction entity mapping users to roles."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("roles.id", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="user_roles",
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="user_roles",
    )
    assigner: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_by],
    )
