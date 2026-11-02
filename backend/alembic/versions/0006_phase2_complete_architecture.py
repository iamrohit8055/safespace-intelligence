"""Phase 2 completion: inspection priority engine, maintenance management, and notifications.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-02 12:30:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Inspection Priority Engine
    # -------------------------------------------------------------------------
    op.create_table(
        "priority_configurations",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sdi_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("urgency_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("unresolved_reports_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("confidence_gap_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "methodology_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_priority_configurations_version"),
        sa.CheckConstraint(
            "sdi_weight >= 0.0 AND sdi_weight <= 1.0",
            name="ck_priority_configurations_sdi_weight",
        ),
        sa.CheckConstraint(
            "urgency_weight >= 0.0 AND urgency_weight <= 1.0",
            name="ck_priority_configurations_urgency_weight",
        ),
        sa.CheckConstraint(
            "unresolved_reports_weight >= 0.0 AND unresolved_reports_weight <= 1.0",
            name="ck_priority_configurations_unresolved_weight",
        ),
        sa.CheckConstraint(
            "confidence_gap_weight >= 0.0 AND confidence_gap_weight <= 1.0",
            name="ck_priority_configurations_confidence_gap_weight",
        ),
    )

    op.create_table(
        "area_priority_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", sa.SmallInteger(), nullable=False),
        sa.Column("priority_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("priority_level", sa.String(length=30), nullable=False),
        sa.Column("sdi_score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("completeness_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "unresolved_reports_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("latest_observation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "never_inspected",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "calculation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "calculation_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["administrative_areas.id"],
            name="fk_area_priority_scores_area_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["priority_configurations.id"],
            name="fk_area_priority_scores_config_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "priority_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT_DATA')",
            name="ck_area_priority_scores_level",
        ),
        sa.CheckConstraint(
            "priority_score IS NULL OR (priority_score >= 0.0 AND priority_score <= 100.0)",
            name="ck_area_priority_scores_bounds",
        ),
        sa.CheckConstraint(
            "unresolved_reports_count >= 0",
            name="ck_area_priority_scores_unresolved_non_negative",
        ),
    )
    op.create_index(
        "uq_area_priority_current",
        "area_priority_scores",
        ["area_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "idx_area_priority_level_score",
        "area_priority_scores",
        ["priority_level", sa.text("priority_score DESC NULLS LAST")],
    )
    op.create_index(
        "idx_area_priority_area_calc",
        "area_priority_scores",
        ["area_id", sa.text("calculation_timestamp DESC")],
    )

    # -------------------------------------------------------------------------
    # 2. Maintenance Management
    # -------------------------------------------------------------------------
    op.create_table(
        "maintenance_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'CREATED'"),
            nullable=False,
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "follow_up_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "allow_duplicate",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("duplicate_override_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_maintenance_tasks_report_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["users.id"],
            name="fk_maintenance_tasks_assigned_to",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_maintenance_tasks_created_by",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_maintenance_tasks_priority",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'CREATED', 'ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED'"
            ")",
            name="ck_maintenance_tasks_status",
        ),
        sa.CheckConstraint(
            "(allow_duplicate = true AND duplicate_override_reason IS NOT NULL) "
            "OR (allow_duplicate = false)",
            name="ck_maintenance_tasks_duplicate_override_reason",
        ),
    )
    op.create_index(
        "uq_maintenance_active_report_task",
        "maintenance_tasks",
        ["report_id"],
        unique=True,
        postgresql_where=sa.text(
            "status NOT IN ('COMPLETED', 'CANCELLED') AND allow_duplicate = false"
        ),
    )
    op.create_index("idx_maintenance_tasks_report", "maintenance_tasks", ["report_id"])
    op.create_index(
        "idx_maintenance_tasks_assigned_status",
        "maintenance_tasks",
        ["assigned_to_user_id", "status"],
    )
    op.create_index(
        "idx_maintenance_tasks_status_created",
        "maintenance_tasks",
        ["status", sa.text("created_at DESC")],
    )
    op.create_index("idx_maintenance_tasks_priority", "maintenance_tasks", ["priority"])

    op.create_table(
        "maintenance_task_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["maintenance_tasks.id"],
            name="fk_maintenance_events_task_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_maintenance_events_actor_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ("
            "'CREATED', 'ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED'"
            ")",
            name="ck_maintenance_events_prev_status",
        ),
        sa.CheckConstraint(
            "new_status IN ("
            "'CREATED', 'ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'CANCELLED'"
            ")",
            name="ck_maintenance_events_new_status",
        ),
    )
    op.create_index(
        "idx_maintenance_events_task_time",
        "maintenance_task_events",
        ["task_id", sa.text("created_at ASC")],
    )

    # -------------------------------------------------------------------------
    # 3. Notification Foundation
    # -------------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name="fk_notifications_recipient_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_notifications_recipient_unread",
        "notifications",
        ["recipient_id", "is_read", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_notifications_recipient_created",
        "notifications",
        ["recipient_id", sa.text("created_at DESC")],
    )

    # -------------------------------------------------------------------------
    # 4. Seed Baseline Priority Configuration v1.0.0
    # -------------------------------------------------------------------------
    priority_configs = sa.table(
        "priority_configurations",
        sa.column("version", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("sdi_weight", sa.Numeric),
        sa.column("urgency_weight", sa.Numeric),
        sa.column("unresolved_reports_weight", sa.Numeric),
        sa.column("confidence_gap_weight", sa.Numeric),
        sa.column("methodology_metadata", postgresql.JSONB),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        priority_configs,
        [
            {
                "version": "v1.0.0",
                "name": "Baseline Inspection Priority Model",
                "description": (
                    "Initial multi-criteria inspection priority model balancing "
                    "SDI deficiency severity (35%), observation latency/staleness (25%), "
                    "unresolved deficiency volume (20%), and confidence gap (20%)."
                ),
                "sdi_weight": 0.3500,
                "urgency_weight": 0.2500,
                "unresolved_reports_weight": 0.2000,
                "confidence_gap_weight": 0.2000,
                "methodology_metadata": json.dumps(
                    {
                        "scale": "0-100",
                        "thresholds": {
                            "CRITICAL": 80.0,
                            "HIGH": 60.0,
                            "MEDIUM": 40.0,
                            "LOW": 0.0,
                        },
                        "staleness_max_days": 30,
                        "unresolved_cap": 20,
                    }
                ),
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    # 3. Notifications
    op.drop_index("idx_notifications_recipient_created", table_name="notifications")
    op.drop_index("idx_notifications_recipient_unread", table_name="notifications")
    op.drop_table("notifications")

    # 2. Maintenance
    op.drop_index("idx_maintenance_events_task_time", table_name="maintenance_task_events")
    op.drop_table("maintenance_task_events")

    op.drop_index("idx_maintenance_tasks_priority", table_name="maintenance_tasks")
    op.drop_index("idx_maintenance_tasks_status_created", table_name="maintenance_tasks")
    op.drop_index("idx_maintenance_tasks_assigned_status", table_name="maintenance_tasks")
    op.drop_index("idx_maintenance_tasks_report", table_name="maintenance_tasks")
    op.drop_index("uq_maintenance_active_report_task", table_name="maintenance_tasks")
    op.drop_table("maintenance_tasks")

    # 1. Inspection Priority
    op.drop_index("idx_area_priority_area_calc", table_name="area_priority_scores")
    op.drop_index("idx_area_priority_level_score", table_name="area_priority_scores")
    op.drop_index("uq_area_priority_current", table_name="area_priority_scores")
    op.drop_table("area_priority_scores")
    op.drop_table("priority_configurations")
