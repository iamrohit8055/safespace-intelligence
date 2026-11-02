"""Report verification, moderation, and audit trail models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.iam import User
    from app.models.reporting import Report


class ReportVerification(Base):
    """Append-only inspection evaluation recorded by authorized personnel."""

    __tablename__ = "report_verifications"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED', 'FLAGGED', 'MARKED_DUPLICATE')",
            name="chk_verification_decision_valid",
        ),
        CheckConstraint(
            "(decision = 'VERIFIED' AND verified_severity IS NOT NULL "
            "AND verified_severity >= 1 AND verified_severity <= 5) OR "
            "(decision <> 'VERIFIED' AND verified_severity IS NULL)",
            name="chk_verification_severity_scale",
        ),
        CheckConstraint(
            "data_confidence_score IS NULL OR "
            "(data_confidence_score >= 0.00 AND data_confidence_score <= 1.00)",
            name="chk_verification_confidence_scale",
        ),
        CheckConstraint(
            "(decision = 'REJECTED' AND rejection_reason IS NOT NULL) OR "
            "(decision <> 'REJECTED' AND rejection_reason IS NULL)",
            name="chk_verification_rejection_reason",
        ),
        Index("idx_verifications_report_id", "report_id", text("verified_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    verifier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_severity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    data_confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="verifications",
    )
    verifier: Mapped["User"] = relationship(
        "User",
        back_populates="verifications",
    )


class ReportStatusHistory(Base):
    """Append-only immutable audit ledger tracking report lifecycle state transitions."""

    __tablename__ = "report_status_history"
    __table_args__ = (
        CheckConstraint(
            "(from_status IS NULL AND to_status = 'SUBMITTED') OR "
            "(from_status IS NOT NULL AND from_status <> to_status)",
            name="chk_status_history_transition_valid",
        ),
        CheckConstraint(
            "(from_status IS NULL OR "
            "from_status IN ('SUBMITTED', 'UNDER_VERIFICATION', "
            "'VERIFIED', 'REJECTED', 'ARCHIVED')) AND "
            "to_status IN ('SUBMITTED', 'UNDER_VERIFICATION', "
            "'VERIFIED', 'REJECTED', 'ARCHIVED')",
            name="chk_status_history_statuses_allowed",
        ),
        Index("idx_status_history_report_id", "report_id", text("created_at ASC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="status_history",
    )
    changed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[changed_by_user_id],
    )
