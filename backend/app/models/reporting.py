"""Infrastructure deficiency reporting models and media references."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
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
    from app.models.iam import User
    from app.models.verification import ReportStatusHistory, ReportVerification


class ReportCategory(Base):
    """Taxonomy of infrastructure deficiency classifications (pure taxonomy, no scoring weights)."""

    __tablename__ = "report_categories"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
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

    # Relationships
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="category",
    )


class Report(Base):
    """Citizen-submitted infrastructure deficiency observation."""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUBMITTED', 'UNDER_VERIFICATION', 'VERIFIED', 'REJECTED', 'ARCHIVED')",
            name="chk_reports_status_valid",
        ),
        CheckConstraint(
            "GeometryType(location) = 'POINT' AND ST_SRID(location) = 4326 "
            "AND NOT ST_IsEmpty(location)",
            name="chk_reports_location_point",
        ),
        CheckConstraint(
            "ST_X(location) >= -180.0 AND ST_X(location) <= 180.0 "
            "AND ST_Y(location) >= -90.0 AND ST_Y(location) <= 90.0",
            name="chk_reports_location_coordinate_bounds",
        ),
        CheckConstraint(
            "duplicate_of_id IS NULL OR duplicate_of_id <> id",
            name="chk_reports_prevent_self_duplicate",
        ),
        Index("idx_reports_location_gist", "location", postgresql_using="gist"),
        Index(
            "idx_reports_location_geog_gist",
            text("((location)::geography)"),
            postgresql_using="gist",
        ),
        Index(
            "idx_reports_status_submitted_at",
            "status",
            text("submitted_at DESC"),
        ),
        Index(
            "idx_reports_admin_area_category",
            "administrative_area_id",
            "category_id",
            postgresql_where=text("status = 'VERIFIED'"),
        ),
        Index(
            "idx_reports_reporter_submitted",
            "reporter_id",
            text("submitted_at DESC"),
        ),
        Index(
            "idx_reports_duplicate_of",
            "duplicate_of_id",
            postgresql_where=text("duplicate_of_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("report_categories.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    administrative_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    address_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default="SUBMITTED",
        server_default=text("'SUBMITTED'"),
        nullable=False,
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    device_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
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
    reporter: Mapped["User"] = relationship(
        "User",
        back_populates="reports",
    )
    category: Mapped["ReportCategory"] = relationship(
        "ReportCategory",
        back_populates="reports",
    )
    administrative_area: Mapped["AdministrativeArea | None"] = relationship(
        "AdministrativeArea",
        back_populates="reports",
    )
    duplicate_of: Mapped["Report | None"] = relationship(
        "Report",
        remote_side=[id],
        back_populates="duplicates",
    )
    duplicates: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="duplicate_of",
    )
    media: Mapped[list["ReportMedia"]] = relationship(
        "ReportMedia",
        back_populates="report",
        passive_deletes="all",
    )
    verifications: Mapped[list["ReportVerification"]] = relationship(
        "ReportVerification",
        back_populates="report",
        passive_deletes="all",
    )
    status_history: Mapped[list["ReportStatusHistory"]] = relationship(
        "ReportStatusHistory",
        back_populates="report",
        passive_deletes="all",
    )


class ReportMedia(Base):
    """External object storage reference and technical metadata for evidence images."""

    __tablename__ = "report_media"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 15728640",
            name="chk_media_file_size_positive",
        ),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="chk_media_mime_type_image_only",
        ),
        CheckConstraint(
            "(width IS NULL OR width > 0) AND (height IS NULL OR height > 0)",
            name="chk_media_dimensions_positive",
        ),
        CheckConstraint(
            "checksum_sha256 ~* '^[a-f0-9]{64}$'",
            name="chk_media_checksum_sha256_format",
        ),
        UniqueConstraint(
            "storage_provider",
            "storage_bucket",
            "storage_key",
            name="uq_report_media_storage_ref",
        ),
        UniqueConstraint(
            "report_id",
            "checksum_sha256",
            name="uq_report_media_report_checksum",
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
    storage_provider: Mapped[str] = mapped_column(
        String(30),
        default="s3",
        server_default=text("'s3'"),
        nullable=False,
    )
    storage_bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="media",
    )
