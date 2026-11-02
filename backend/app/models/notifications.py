"""In-app notification models for notifying citizens, verifiers, and maintenance personnel."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.iam import User


class Notification(Base):
    """Database-backed in-app notification record for system alerts and lifecycle events."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=expression.false(),
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    recipient: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index(
            "idx_notifications_recipient_unread",
            "recipient_id",
            "is_read",
            text("created_at DESC"),
        ),
        Index(
            "idx_notifications_recipient_created",
            "recipient_id",
            text("created_at DESC"),
        ),
    )
