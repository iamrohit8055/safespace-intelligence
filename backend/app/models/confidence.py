"""SQLAlchemy models for individual report evidence confidence and area-level confidence."""

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
    from app.models.reporting import Report, ReportCategory


class ConfidenceConfiguration(Base):
    """Versioned methodology and factor weighting configuration for evidence confidence."""

    __tablename__ = "confidence_configurations"

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
    factors: Mapped[list["ConfidenceConfigurationFactor"]] = relationship(
        "ConfidenceConfigurationFactor",
        back_populates="configuration",
        cascade="all, delete-orphan",
    )
    report_scores: Mapped[list["ReportConfidenceScore"]] = relationship(
        "ReportConfidenceScore",
        back_populates="configuration",
    )
    area_scores: Mapped[list["AreaConfidenceScore"]] = relationship(
        "AreaConfidenceScore",
        back_populates="configuration",
    )


class ConfidenceConfigurationFactor(Base):
    """Factor definition and weight within a confidence methodology version."""

    __tablename__ = "confidence_configuration_factors"
    __table_args__ = (
        CheckConstraint(
            "weight >= 0.0000 AND weight <= 1.0000",
            name="chk_conf_factor_weight_bounds",
        ),
        UniqueConstraint(
            "configuration_id",
            "factor_code",
            name="uq_conf_config_factor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    configuration_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("confidence_configurations.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    factor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    is_measurable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    unavailability_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    configuration: Mapped["ConfidenceConfiguration"] = relationship(
        "ConfidenceConfiguration",
        back_populates="factors",
    )


class ReportConfidenceScore(Base):
    """Calculated evidence confidence assessment for an individual report."""

    __tablename__ = "report_confidence_scores"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0.0000 AND confidence_score <= 1.0000)",
            name="chk_report_conf_score_bounds",
        ),
        CheckConstraint(
            "completeness_pct >= 0.00 AND completeness_pct <= 100.00",
            name="chk_report_conf_completeness",
        ),
        CheckConstraint(
            "available_factors_count >= 0 AND total_factors_count > 0",
            name="chk_report_conf_counts",
        ),
        Index(
            "uq_report_confidence_current",
            "report_id",
            "configuration_id",
            unique=True,
            postgresql_where=text("is_current = True"),
        ),
        Index(
            "idx_report_conf_report_timestamp",
            "report_id",
            text("calculation_timestamp DESC"),
        ),
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
    configuration_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("confidence_configurations.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    completeness_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    available_factors_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_factors_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=expression.true(),
        nullable=False,
    )
    factor_details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    calculation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    report: Mapped["Report"] = relationship("Report")
    configuration: Mapped["ConfidenceConfiguration"] = relationship(
        "ConfidenceConfiguration",
        back_populates="report_scores",
    )
    components: Mapped[list["ReportConfidenceComponent"]] = relationship(
        "ReportConfidenceComponent",
        back_populates="report_confidence",
        cascade="all, delete-orphan",
    )


class ReportConfidenceComponent(Base):
    """Granular factor evaluation contributing to an individual ReportConfidenceScore."""

    __tablename__ = "report_confidence_components"
    __table_args__ = (
        CheckConstraint(
            "factor_score IS NULL OR (factor_score >= 0.0000 AND factor_score <= 1.0000)",
            name="chk_rep_conf_comp_score",
        ),
        CheckConstraint(
            "assigned_weight >= 0.0000 AND assigned_weight <= 1.0000",
            name="chk_rep_conf_comp_weight",
        ),
        CheckConstraint(
            "normalized_weight IS NULL OR "
            "(normalized_weight >= 0.0000 AND normalized_weight <= 1.0000)",
            name="chk_rep_conf_comp_norm_weight",
        ),
        CheckConstraint(
            "availability_state IN ('OBSERVED', 'UNAVAILABLE')",
            name="chk_rep_conf_comp_avail",
        ),
        UniqueConstraint(
            "report_confidence_id",
            "factor_code",
            name="uq_rep_conf_comp_factor",
        ),
        Index("idx_rep_conf_comp_score_id", "report_confidence_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    report_confidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_confidence_scores.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    factor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    factor_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    assigned_weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    normalized_weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    weighted_contribution: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    availability_state: Mapped[str] = mapped_column(String(30), nullable=False)
    unavailability_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    report_confidence: Mapped["ReportConfidenceScore"] = relationship(
        "ReportConfidenceScore",
        back_populates="components",
    )


class AreaConfidenceScore(Base):
    """Calculated evidence confidence and completeness metrics for an administrative area."""

    __tablename__ = "area_confidence_scores"
    __table_args__ = (
        CheckConstraint(
            "area_confidence_score IS NULL OR "
            "(area_confidence_score >= 0.0000 AND area_confidence_score <= 1.0000)",
            name="chk_area_conf_score_bounds",
        ),
        CheckConstraint(
            "confidence_completeness_pct >= 0.00 AND confidence_completeness_pct <= 100.00",
            name="chk_area_conf_completeness",
        ),
        CheckConstraint(
            "total_reports_count >= 0 AND reports_with_confidence_count >= 0 "
            "AND reports_without_confidence_count >= 0",
            name="chk_area_conf_counts",
        ),
        Index(
            "uq_area_confidence_current",
            "administrative_area_id",
            "configuration_id",
            unique=True,
            postgresql_where=text("is_current = True"),
        ),
        Index(
            "idx_area_confidence_area_timestamp",
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
        ForeignKey("confidence_configurations.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    area_confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confidence_completeness_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    total_reports_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reports_with_confidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reports_without_confidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
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
    methodology_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    # Relationships
    administrative_area: Mapped["AdministrativeArea"] = relationship("AdministrativeArea")
    configuration: Mapped["ConfidenceConfiguration"] = relationship(
        "ConfidenceConfiguration",
        back_populates="area_scores",
    )
    components: Mapped[list["AreaConfidenceComponent"]] = relationship(
        "AreaConfidenceComponent",
        back_populates="area_confidence",
        cascade="all, delete-orphan",
    )


class AreaConfidenceComponent(Base):
    """Category-level evidence confidence contribution within an AreaConfidenceScore."""

    __tablename__ = "area_confidence_components"
    __table_args__ = (
        CheckConstraint(
            "category_confidence_score IS NULL OR "
            "(category_confidence_score >= 0.0000 AND category_confidence_score <= 1.0000)",
            name="chk_area_conf_comp_score",
        ),
        CheckConstraint(
            "report_count >= 0 AND confident_report_count >= 0",
            name="chk_area_conf_comp_counts",
        ),
        CheckConstraint(
            "availability_state IN ('OBSERVED', 'INSUFFICIENT_DATA')",
            name="chk_area_conf_comp_avail",
        ),
        UniqueConstraint(
            "area_confidence_id",
            "category_id",
            name="uq_area_conf_comp_category",
        ),
        Index("idx_area_conf_comp_score_id", "area_confidence_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    area_confidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("area_confidence_scores.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("report_categories.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    category_confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confident_report_count: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_state: Mapped[str] = mapped_column(String(30), nullable=False)

    # Relationships
    area_confidence: Mapped["AreaConfidenceScore"] = relationship(
        "AreaConfidenceScore",
        back_populates="components",
    )
    category: Mapped["ReportCategory"] = relationship("ReportCategory")
