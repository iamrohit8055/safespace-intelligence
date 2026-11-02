"""Intelligence engine models for versioned scoring configurations and SDI results."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.geography import AdministrativeArea
    from app.models.reporting import ReportCategory


class ScoringConfiguration(Base):
    """Versioned methodology and category weighting configuration for SDI calculations."""

    __tablename__ = "scoring_configurations"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    methodology_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
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

    # Relationships
    weights: Mapped[list["ScoringConfigurationWeight"]] = relationship(
        "ScoringConfigurationWeight",
        back_populates="configuration",
        cascade="all, delete-orphan",
    )
    scores: Mapped[list["AreaScore"]] = relationship(
        "AreaScore",
        back_populates="configuration",
    )


class ScoringConfigurationWeight(Base):
    """Category weight assignment within a specific scoring configuration version."""

    __tablename__ = "scoring_configuration_weights"
    __table_args__ = (
        CheckConstraint(
            "weight >= 0.0000 AND weight <= 1.0000",
            name="chk_config_weight_bounds",
        ),
        UniqueConstraint(
            "configuration_id",
            "category_id",
            name="uq_config_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("scoring_configurations.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("report_categories.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    configuration: Mapped["ScoringConfiguration"] = relationship(
        "ScoringConfiguration",
        back_populates="weights",
    )
    category: Mapped["ReportCategory"] = relationship("ReportCategory")


class AreaScore(Base):
    """Calculated Safety Deficiency Index (SDI) for an administrative jurisdiction."""

    __tablename__ = "area_scores"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score >= 0.00 AND score <= 100.00)",
            name="chk_area_scores_score_bounds",
        ),
        CheckConstraint(
            "completeness_pct >= 0.00 AND completeness_pct <= 100.00",
            name="chk_area_scores_completeness_bounds",
        ),
        CheckConstraint(
            "participating_categories_count >= 0 AND total_categories_count > 0 "
            "AND eligible_reports_count >= 0",
            name="chk_area_scores_counts_positive",
        ),
        Index(
            "uq_area_scores_current",
            "administrative_area_id",
            "configuration_id",
            unique=True,
            postgresql_where=text("is_current = True"),
        ),
        Index(
            "idx_area_scores_area_timestamp",
            "administrative_area_id",
            text("calculation_timestamp DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    administrative_area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    configuration_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("scoring_configurations.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    completeness_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    participating_categories_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_categories_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    eligible_reports_count: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    methodology_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    # Relationships
    administrative_area: Mapped["AdministrativeArea"] = relationship("AdministrativeArea")
    configuration: Mapped["ScoringConfiguration"] = relationship(
        "ScoringConfiguration",
        back_populates="scores",
    )
    components: Mapped[list["ScoreComponent"]] = relationship(
        "ScoreComponent",
        back_populates="area_score",
        cascade="all, delete-orphan",
    )


class ScoreComponent(Base):
    """Category-level deficiency score contribution within an AreaScore calculation."""

    __tablename__ = "score_components"
    __table_args__ = (
        CheckConstraint(
            "category_score IS NULL OR (category_score >= 0.00 AND category_score <= 100.00)",
            name="chk_score_components_category_score",
        ),
        CheckConstraint(
            "assigned_weight >= 0.0000 AND assigned_weight <= 1.0000",
            name="chk_score_components_assigned_weight",
        ),
        CheckConstraint(
            "normalized_weight IS NULL OR "
            "(normalized_weight >= 0.0000 AND normalized_weight <= 1.0000)",
            name="chk_score_components_normalized_weight",
        ),
        CheckConstraint(
            "availability_state IN ('OBSERVED', 'INSUFFICIENT_DATA')",
            name="chk_score_components_availability",
        ),
        CheckConstraint(
            "report_count >= 0",
            name="chk_score_components_report_count",
        ),
        UniqueConstraint(
            "area_score_id",
            "category_id",
            name="uq_score_component_area_category",
        ),
        Index("idx_score_components_area_score_id", "area_score_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    area_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("area_scores.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("report_categories.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    category_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    assigned_weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    normalized_weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    weighted_contribution: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_state: Mapped[str] = mapped_column(String(30), nullable=False)

    # Relationships
    area_score: Mapped["AreaScore"] = relationship(
        "AreaScore",
        back_populates="components",
    )
    category: Mapped["ReportCategory"] = relationship("ReportCategory")
