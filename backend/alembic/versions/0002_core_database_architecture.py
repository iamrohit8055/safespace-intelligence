"""Core database architecture: Nine core domain tables and constraints.

Revision ID: 0002
Revises: 0001_enable_postgis
Create Date: 2026-11-02 01:45:00.000000

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001_enable_postgis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all nine core domain tables, constraints, and indexes."""
    # 1. roles
    op.create_table(
        "roles",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. users
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="chk_users_email_format",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_users_email_lower",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
    )

    # 3. user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # 4. administrative_areas
    op.create_table(
        "administrative_areas",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("area_type", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column(
            "boundary",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "area_type IN ('municipality', 'district', 'ward', 'zone')",
            name="chk_admin_area_type",
        ),
        sa.CheckConstraint(
            "ST_IsValid(boundary) AND NOT ST_IsEmpty(boundary)",
            name="chk_admin_area_boundary_valid",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="chk_admin_area_prevent_self_parent",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["administrative_areas.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "idx_admin_areas_boundary_gist",
        "administrative_areas",
        ["boundary"],
        unique=False,
        postgresql_using="gist",
    )

    # 5. report_categories
    op.create_table(
        "report_categories",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # 6. reports
    op.create_table(
        "reports",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("administrative_area_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("address_text", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'SUBMITTED'"),
            nullable=False,
        ),
        sa.Column("duplicate_of_id", sa.UUID(), nullable=True),
        sa.Column(
            "device_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('SUBMITTED', 'UNDER_VERIFICATION', 'VERIFIED', 'REJECTED', 'ARCHIVED')",
            name="chk_reports_status_valid",
        ),
        sa.CheckConstraint(
            "GeometryType(location) = 'POINT' AND ST_SRID(location) = 4326 "
            "AND NOT ST_IsEmpty(location)",
            name="chk_reports_location_point",
        ),
        sa.CheckConstraint(
            "ST_X(location) >= -180.0 AND ST_X(location) <= 180.0 "
            "AND ST_Y(location) >= -90.0 AND ST_Y(location) <= 90.0",
            name="chk_reports_location_coordinate_bounds",
        ),
        sa.CheckConstraint(
            "duplicate_of_id IS NULL OR duplicate_of_id <> id",
            name="chk_reports_prevent_self_duplicate",
        ),
        sa.ForeignKeyConstraint(
            ["administrative_area_id"],
            ["administrative_areas.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["report_categories.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["reports.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_reports_location_gist",
        "reports",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_reports_location_geog_gist",
        "reports",
        [sa.literal_column("((location)::geography)")],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_reports_status_submitted_at",
        "reports",
        ["status", sa.literal_column("submitted_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_reports_admin_area_category",
        "reports",
        ["administrative_area_id", "category_id"],
        unique=False,
        postgresql_where=sa.text("status = 'VERIFIED'"),
    )
    op.create_index(
        "idx_reports_reporter_submitted",
        "reports",
        ["reporter_id", sa.literal_column("submitted_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_reports_duplicate_of",
        "reports",
        ["duplicate_of_id"],
        unique=False,
        postgresql_where=sa.text("duplicate_of_id IS NOT NULL"),
    )

    # 7. report_media
    op.create_table(
        "report_media",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column(
            "storage_provider",
            sa.String(length=30),
            server_default=sa.text("'s3'"),
            nullable=False,
        ),
        sa.Column("storage_bucket", sa.String(length=63), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "technical_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 15728640",
            name="chk_media_file_size_positive",
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="chk_media_mime_type_image_only",
        ),
        sa.CheckConstraint(
            "(width IS NULL OR width > 0) AND (height IS NULL OR height > 0)",
            name="chk_media_dimensions_positive",
        ),
        sa.CheckConstraint(
            "checksum_sha256 ~* '^[a-f0-9]{64}$'",
            name="chk_media_checksum_sha256_format",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_provider",
            "storage_bucket",
            "storage_key",
            name="uq_report_media_storage_ref",
        ),
        sa.UniqueConstraint(
            "report_id",
            "checksum_sha256",
            name="uq_report_media_report_checksum",
        ),
    )

    # 8. report_verifications
    op.create_table(
        "report_verifications",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("verifier_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("rejection_reason", sa.String(length=50), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("verified_severity", sa.SmallInteger(), nullable=True),
        sa.Column("data_confidence_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED', 'FLAGGED', 'MARKED_DUPLICATE')",
            name="chk_verification_decision_valid",
        ),
        sa.CheckConstraint(
            "(decision = 'VERIFIED' AND verified_severity IS NOT NULL "
            "AND verified_severity >= 1 AND verified_severity <= 5) OR "
            "(decision <> 'VERIFIED' AND verified_severity IS NULL)",
            name="chk_verification_severity_scale",
        ),
        sa.CheckConstraint(
            "data_confidence_score IS NULL OR "
            "(data_confidence_score >= 0.00 AND data_confidence_score <= 1.00)",
            name="chk_verification_confidence_scale",
        ),
        sa.CheckConstraint(
            "(decision = 'REJECTED' AND rejection_reason IS NOT NULL) OR "
            "(decision <> 'REJECTED' AND rejection_reason IS NULL)",
            name="chk_verification_rejection_reason",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verifier_id"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_verifications_report_id",
        "report_verifications",
        ["report_id", sa.literal_column("verified_at DESC")],
        unique=False,
    )

    # 9. report_status_history
    op.create_table(
        "report_status_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(from_status IS NULL AND to_status = 'SUBMITTED') OR "
            "(from_status IS NOT NULL AND from_status <> to_status)",
            name="chk_status_history_transition_valid",
        ),
        sa.CheckConstraint(
            "(from_status IS NULL OR "
            "from_status IN ('SUBMITTED', 'UNDER_VERIFICATION', "
            "'VERIFIED', 'REJECTED', 'ARCHIVED')) AND "
            "to_status IN ('SUBMITTED', 'UNDER_VERIFICATION', "
            "'VERIFIED', 'REJECTED', 'ARCHIVED')",
            name="chk_status_history_statuses_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_status_history_report_id",
        "report_status_history",
        ["report_id", sa.literal_column("created_at ASC")],
        unique=False,
    )


def downgrade() -> None:
    """Drop objects introduced by revision 0002 in reverse dependency order."""
    op.drop_index("idx_status_history_report_id", table_name="report_status_history")
    op.drop_table("report_status_history")

    op.drop_index("idx_verifications_report_id", table_name="report_verifications")
    op.drop_table("report_verifications")

    op.drop_table("report_media")

    op.drop_index(
        "idx_reports_admin_area_category",
        table_name="reports",
        postgresql_where=sa.text("status = 'VERIFIED'"),
    )
    op.drop_index(
        "idx_reports_duplicate_of",
        table_name="reports",
        postgresql_where=sa.text("duplicate_of_id IS NOT NULL"),
    )
    op.drop_index(
        "idx_reports_location_geog_gist",
        table_name="reports",
        postgresql_using="gist",
    )
    op.drop_index(
        "idx_reports_location_gist",
        table_name="reports",
        postgresql_using="gist",
    )
    op.drop_index("idx_reports_reporter_submitted", table_name="reports")
    op.drop_index("idx_reports_status_submitted_at", table_name="reports")
    op.drop_table("reports")

    op.drop_table("report_categories")

    op.drop_index(
        "idx_admin_areas_boundary_gist",
        table_name="administrative_areas",
        postgresql_using="gist",
    )
    op.drop_table("administrative_areas")

    op.drop_table("user_roles")

    op.drop_index("idx_users_email_lower", table_name="users")
    op.drop_table("users")

    op.drop_table("roles")
