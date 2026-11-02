"""Inspection priority models for versioned priority configurations and area priority scores."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.geography import AdministrativeArea


class PriorityConfiguration(Base):
    """Versioned configuration for calculating municipal infrastructure inspection priorities."""

    __tablename__ = "priority_configurations"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sdi_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    urgency_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    unresolved_reports_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    confidence_gap_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    methodology_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    scores: Mapped[list["AreaPriorityScore"]] = relationship(
        "AreaPriorityScore",
        back_populates="configuration",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "sdi_weight >= 0.0 AND sdi_weight <= 1.0",
            name="ck_priority_configurations_sdi_weight",
        ),
        CheckConstraint(
            "urgency_weight >= 0.0 AND urgency_weight <= 1.0",
            name="ck_priority_configurations_urgency_weight",
        ),
        CheckConstraint(
            "unresolved_reports_weight >= 0.0 AND unresolved_reports_weight <= 1.0",
            name="ck_priority_configurations_unresolved_weight",
        ),
        CheckConstraint(
            "confidence_gap_weight >= 0.0 AND confidence_gap_weight <= 1.0",
            name="ck_priority_configurations_confidence_gap_weight",
        ),
    )


class AreaPriorityScore(Base):
    """Calculated infrastructure inspection priority for a municipal administrative area."""

    __tablename__ = "area_priority_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    configuration_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("priority_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    priority_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    priority_level: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    sdi_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2),
        nullable=True,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    completeness_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    unresolved_reports_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    latest_observation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_inspected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    never_inspected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=expression.false(),
        nullable=False,
    )
    calculation_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    calculation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    area: Mapped["AdministrativeArea"] = relationship("AdministrativeArea")
    configuration: Mapped["PriorityConfiguration"] = relationship(
        "PriorityConfiguration", back_populates="scores"
    )

    __table_args__ = (
        CheckConstraint(
            "priority_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT_DATA')",
            name="ck_area_priority_scores_level",
        ),
        CheckConstraint(
            "priority_score IS NULL OR (priority_score >= 0.0 AND priority_score <= 100.0)",
            name="ck_area_priority_scores_bounds",
        ),
        CheckConstraint(
            "unresolved_reports_count >= 0",
            name="ck_area_priority_scores_unresolved_non_negative",
        ),
        Index(
            "uq_area_priority_current",
            "area_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index(
            "idx_area_priority_level_score",
            "priority_level",
            text("priority_score DESC NULLS LAST"),
        ),
        Index(
            "idx_area_priority_area_calc",
            "area_id",
            text("calculation_timestamp DESC"),
        ),
    )
