"""SQLAlchemy models for duplicate candidate detection, duplicate review, and linking."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
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


class DuplicateDetectionConfiguration(Base):
    """Configuration defining spatial and temporal thresholds for candidate deduplication."""

    __tablename__ = "duplicate_detection_configurations"
    __table_args__ = (
        CheckConstraint(
            "spatial_radius_metres > 0.00",
            name="chk_dup_config_radius_pos",
        ),
        CheckConstraint(
            "time_window_days > 0",
            name="chk_dup_config_window_pos",
        ),
    )

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    spatial_radius_metres: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        default=Decimal("50.00"),
        server_default=text("50.00"),
        nullable=False,
    )
    time_window_days: Mapped[int] = mapped_column(
        Integer,
        default=30,
        server_default=text("30"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
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


class DuplicateCandidate(Base):
    """Pair of reports identified as potential duplicates based on spatial/temporal proximity."""

    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        CheckConstraint(
            "first_report_id < second_report_id",
            name="chk_candidate_pair_order",
        ),
        CheckConstraint(
            "distance_metres >= 0.00",
            name="chk_candidate_distance_pos",
        ),
        CheckConstraint(
            "time_difference_seconds >= 0",
            name="chk_candidate_time_diff_pos",
        ),
        CheckConstraint(
            "review_status IN ('PENDING', 'CONFIRMED_DUPLICATE', 'NOT_DUPLICATE', 'NEEDS_REVIEW')",
            name="chk_candidate_status_valid",
        ),
        UniqueConstraint(
            "first_report_id",
            "second_report_id",
            name="uq_duplicate_candidates_pair",
        ),
        Index("idx_dup_candidates_first", "first_report_id"),
        Index("idx_dup_candidates_second", "second_report_id"),
        Index("idx_dup_candidates_status", "review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    first_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    second_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    distance_metres: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    time_difference_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        server_default=text("'PENDING'"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    first_report: Mapped["Report"] = relationship("Report", foreign_keys=[first_report_id])
    second_report: Mapped["Report"] = relationship("Report", foreign_keys=[second_report_id])
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewer_id])
    review_history: Mapped[list["DuplicateReviewHistory"]] = relationship(
        "DuplicateReviewHistory",
        back_populates="candidate",
    )


class DuplicateReviewHistory(Base):
    """Immutable audit trail of duplicate moderation decisions and canonical links."""

    __tablename__ = "duplicate_review_history"
    __table_args__ = (
        CheckConstraint(
            "duplicate_report_id <> canonical_report_id",
            name="chk_dup_history_distinct",
        ),
        CheckConstraint(
            "decision IN ('CONFIRMED_DUPLICATE', 'NOT_DUPLICATE', 'NEEDS_REVIEW')",
            name="chk_dup_history_decision_valid",
        ),
        Index("idx_dup_history_duplicate_report", "duplicate_report_id"),
        Index("idx_dup_history_canonical_report", "canonical_report_id"),
        Index("idx_dup_history_reviewer", "reviewer_id"),
        Index("idx_dup_history_timestamp", text("reviewed_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("duplicate_candidates.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    duplicate_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    canonical_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    candidate: Mapped["DuplicateCandidate | None"] = relationship(
        "DuplicateCandidate",
        back_populates="review_history",
    )
    duplicate_report: Mapped["Report"] = relationship("Report", foreign_keys=[duplicate_report_id])
    canonical_report: Mapped["Report"] = relationship("Report", foreign_keys=[canonical_report_id])
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewer_id])
