"""Maintenance lifecycle models for managing infrastructure repair tasks and audit events."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
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
    from app.models.reporting import Report


class MaintenanceTask(Base):
    """Infrastructure maintenance repair task linked to a verified deficiency report."""

    __tablename__ = "maintenance_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CREATED",
        server_default=text("'CREATED'"),
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    follow_up_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=expression.false(),
        nullable=False,
    )
    allow_duplicate: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=expression.false(),
        nullable=False,
    )
    duplicate_override_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    report: Mapped["Report"] = relationship("Report")
    assigned_to: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_to_user_id])
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    events: Mapped[list["MaintenanceTaskEvent"]] = relationship(
        "MaintenanceTaskEvent",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="MaintenanceTaskEvent.created_at.asc()",
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_maintenance_tasks_priority",
        ),
        CheckConstraint(
            "status IN ("
            "'CREATED', 'ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED'"
            ")",
            name="ck_maintenance_tasks_status",
        ),
        CheckConstraint(
            "(allow_duplicate = true AND duplicate_override_reason IS NOT NULL) "
            "OR (allow_duplicate = false)",
            name="ck_maintenance_tasks_duplicate_override_reason",
        ),
        Index(
            "uq_maintenance_active_report_task",
            "report_id",
            unique=True,
            postgresql_where=text(
                "status NOT IN ('COMPLETED', 'CANCELLED') AND allow_duplicate = false"
            ),
        ),
        Index("idx_maintenance_tasks_report", "report_id"),
        Index("idx_maintenance_tasks_assigned_status", "assigned_to_user_id", "status"),
        Index("idx_maintenance_tasks_status_created", "status", text("created_at DESC")),
        Index("idx_maintenance_tasks_priority", "priority"),
    )


class MaintenanceTaskEvent(Base):
    """Immutable audit event log for maintenance task lifecycle state transitions."""

    __tablename__ = "maintenance_task_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    previous_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    task: Mapped["MaintenanceTask"] = relationship("MaintenanceTask", back_populates="events")
    actor: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ("
            "'CREATED', 'ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED'"
            ")",
            name="ck_maintenance_events_prev_status",
        ),
        CheckConstraint(
            "new_status IN ("
            "'CREATED', 'ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED'"
            ")",
            name="ck_maintenance_events_new_status",
        ),
        Index("idx_maintenance_events_task_time", "task_id", text("created_at ASC")),
    )
