"""Geospatial administrative boundaries and jurisdictional models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.reporting import Report


class AdministrativeArea(Base):
    """Hierarchical municipal jurisdiction boundary (ward, district, municipality)."""

    __tablename__ = "administrative_areas"
    __table_args__ = (
        CheckConstraint(
            "area_type IN ('municipality', 'district', 'ward', 'zone')",
            name="chk_admin_area_type",
        ),
        CheckConstraint(
            "ST_IsValid(boundary) AND NOT ST_IsEmpty(boundary)",
            name="chk_admin_area_boundary_valid",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="chk_admin_area_prevent_self_parent",
        ),
        Index("idx_admin_areas_boundary_gist", "boundary", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    area_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    boundary: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
        nullable=False,
    )
    properties: Mapped[dict[str, Any]] = mapped_column(
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
    parent: Mapped["AdministrativeArea | None"] = relationship(
        "AdministrativeArea",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["AdministrativeArea"]] = relationship(
        "AdministrativeArea",
        back_populates="parent",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="administrative_area",
    )
