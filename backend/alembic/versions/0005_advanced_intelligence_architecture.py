"""Advanced intelligence engine: duplicate detection, duplicate review, and evidence confidence.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-02 11:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. duplicate_detection_configurations
    op.create_table(
        "duplicate_detection_configurations",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "spatial_radius_metres",
            sa.Numeric(precision=6, scale=2),
            server_default=sa.text("50.00"),
            nullable=False,
        ),
        sa.Column(
            "time_window_days",
            sa.Integer(),
            server_default=sa.text("30"),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_duplicate_detection_config_version"),
        sa.CheckConstraint(
            "spatial_radius_metres > 0.00",
            name="chk_dup_config_radius_pos",
        ),
        sa.CheckConstraint(
            "time_window_days > 0",
            name="chk_dup_config_window_pos",
        ),
    )

    # 2. duplicate_candidates
    op.create_table(
        "duplicate_candidates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("first_report_id", sa.UUID(), nullable=False),
        sa.Column("second_report_id", sa.UUID(), nullable=False),
        sa.Column("distance_metres", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("time_difference_seconds", sa.BigInteger(), nullable=False),
        sa.Column("rule_version", sa.String(length=50), nullable=False),
        sa.Column(
            "review_status",
            sa.String(length=30),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["first_report_id"],
            ["reports.id"],
            name="fk_dup_candidates_first_report",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["second_report_id"],
            ["reports.id"],
            name="fk_dup_candidates_second_report",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            name="fk_dup_candidates_reviewer",
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "first_report_id < second_report_id",
            name="chk_candidate_pair_order",
        ),
        sa.CheckConstraint(
            "distance_metres >= 0.00",
            name="chk_candidate_distance_pos",
        ),
        sa.CheckConstraint(
            "time_difference_seconds >= 0",
            name="chk_candidate_time_diff_pos",
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'CONFIRMED_DUPLICATE', 'NOT_DUPLICATE', 'NEEDS_REVIEW')",
            name="chk_candidate_status_valid",
        ),
        sa.UniqueConstraint(
            "first_report_id",
            "second_report_id",
            name="uq_duplicate_candidates_pair",
        ),
    )
    op.create_index(
        "idx_dup_candidates_first",
        "duplicate_candidates",
        ["first_report_id"],
    )
    op.create_index(
        "idx_dup_candidates_second",
        "duplicate_candidates",
        ["second_report_id"],
    )
    op.create_index(
        "idx_dup_candidates_status",
        "duplicate_candidates",
        ["review_status"],
    )

    # 3. duplicate_review_history
    op.create_table(
        "duplicate_review_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=True),
        sa.Column("duplicate_report_id", sa.UUID(), nullable=False),
        sa.Column("canonical_report_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["duplicate_candidates.id"],
            name="fk_dup_history_candidate",
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_report_id"],
            ["reports.id"],
            name="fk_dup_history_duplicate_report",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_report_id"],
            ["reports.id"],
            name="fk_dup_history_canonical_report",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            name="fk_dup_history_reviewer",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "duplicate_report_id <> canonical_report_id",
            name="chk_dup_history_distinct",
        ),
        sa.CheckConstraint(
            "decision IN ('CONFIRMED_DUPLICATE', 'NOT_DUPLICATE', 'NEEDS_REVIEW')",
            name="chk_dup_history_decision_valid",
        ),
    )
    op.create_index(
        "idx_dup_history_duplicate_report",
        "duplicate_review_history",
        ["duplicate_report_id"],
    )
    op.create_index(
        "idx_dup_history_canonical_report",
        "duplicate_review_history",
        ["canonical_report_id"],
    )
    op.create_index(
        "idx_dup_history_reviewer",
        "duplicate_review_history",
        ["reviewer_id"],
    )
    op.create_index(
        "idx_dup_history_timestamp",
        "duplicate_review_history",
        [sa.text("reviewed_at DESC")],
    )

    # 4. confidence_configurations
    op.create_table(
        "confidence_configurations",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "methodology_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("version", name="uq_confidence_configurations_version"),
    )

    # 5. confidence_configuration_factors
    op.create_table(
        "confidence_configuration_factors",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("configuration_id", sa.SmallInteger(), nullable=False),
        sa.Column("factor_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "is_measurable",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("unavailability_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["confidence_configurations.id"],
            name="fk_conf_factors_configuration",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "weight >= 0.0000 AND weight <= 1.0000",
            name="chk_conf_factor_weight_bounds",
        ),
        sa.UniqueConstraint(
            "configuration_id",
            "factor_code",
            name="uq_conf_config_factor",
        ),
    )

    # 6. report_confidence_scores
    op.create_table(
        "report_confidence_scores",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("configuration_id", sa.SmallInteger(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("completeness_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("available_factors_count", sa.SmallInteger(), nullable=False),
        sa.Column("total_factors_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "factor_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "calculation_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_report_confidence_report",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["confidence_configurations.id"],
            name="fk_report_confidence_config",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0.0000 AND confidence_score <= 1.0000)",
            name="chk_report_conf_score_bounds",
        ),
        sa.CheckConstraint(
            "completeness_pct >= 0.00 AND completeness_pct <= 100.00",
            name="chk_report_conf_completeness",
        ),
        sa.CheckConstraint(
            "available_factors_count >= 0 AND total_factors_count > 0",
            name="chk_report_conf_counts",
        ),
    )
    op.create_index(
        "uq_report_confidence_current",
        "report_confidence_scores",
        ["report_id", "configuration_id"],
        unique=True,
        postgresql_where=sa.text("is_current = True"),
    )
    op.create_index(
        "idx_report_conf_report_timestamp",
        "report_confidence_scores",
        ["report_id", sa.text("calculation_timestamp DESC")],
    )

    # 7. report_confidence_components
    op.create_table(
        "report_confidence_components",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("report_confidence_id", sa.UUID(), nullable=False),
        sa.Column("factor_code", sa.String(length=50), nullable=False),
        sa.Column("factor_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("assigned_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("normalized_weight", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("weighted_contribution", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("availability_state", sa.String(length=30), nullable=False),
        sa.Column("unavailability_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["report_confidence_id"],
            ["report_confidence_scores.id"],
            name="fk_report_conf_components_score",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "factor_score IS NULL OR (factor_score >= 0.0000 AND factor_score <= 1.0000)",
            name="chk_rep_conf_comp_score",
        ),
        sa.CheckConstraint(
            "assigned_weight >= 0.0000 AND assigned_weight <= 1.0000",
            name="chk_rep_conf_comp_weight",
        ),
        sa.CheckConstraint(
            "normalized_weight IS NULL OR "
            "(normalized_weight >= 0.0000 AND normalized_weight <= 1.0000)",
            name="chk_rep_conf_comp_norm_weight",
        ),
        sa.CheckConstraint(
            "availability_state IN ('OBSERVED', 'UNAVAILABLE')",
            name="chk_rep_conf_comp_avail",
        ),
        sa.UniqueConstraint(
            "report_confidence_id",
            "factor_code",
            name="uq_rep_conf_comp_factor",
        ),
    )
    op.create_index(
        "idx_rep_conf_comp_score_id",
        "report_confidence_components",
        ["report_confidence_id"],
    )

    # 8. area_confidence_scores
    op.create_table(
        "area_confidence_scores",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("administrative_area_id", sa.UUID(), nullable=False),
        sa.Column("configuration_id", sa.SmallInteger(), nullable=False),
        sa.Column("area_confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("confidence_completeness_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("total_reports_count", sa.Integer(), nullable=False),
        sa.Column("reports_with_confidence_count", sa.Integer(), nullable=False),
        sa.Column("reports_without_confidence_count", sa.Integer(), nullable=False),
        sa.Column(
            "calculation_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "methodology_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["administrative_area_id"],
            ["administrative_areas.id"],
            name="fk_area_confidence_area",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["confidence_configurations.id"],
            name="fk_area_confidence_config",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "area_confidence_score IS NULL OR "
            "(area_confidence_score >= 0.0000 AND area_confidence_score <= 1.0000)",
            name="chk_area_conf_score_bounds",
        ),
        sa.CheckConstraint(
            "confidence_completeness_pct >= 0.00 AND confidence_completeness_pct <= 100.00",
            name="chk_area_conf_completeness",
        ),
        sa.CheckConstraint(
            "total_reports_count >= 0 AND reports_with_confidence_count >= 0 "
            "AND reports_without_confidence_count >= 0",
            name="chk_area_conf_counts",
        ),
    )
    op.create_index(
        "uq_area_confidence_current",
        "area_confidence_scores",
        ["administrative_area_id", "configuration_id"],
        unique=True,
        postgresql_where=sa.text("is_current = True"),
    )
    op.create_index(
        "idx_area_confidence_area_timestamp",
        "area_confidence_scores",
        ["administrative_area_id", sa.text("calculation_timestamp DESC")],
    )

    # 9. area_confidence_components
    op.create_table(
        "area_confidence_components",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("area_confidence_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("category_confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("confident_report_count", sa.Integer(), nullable=False),
        sa.Column("availability_state", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["area_confidence_id"],
            ["area_confidence_scores.id"],
            name="fk_area_conf_comp_score",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["report_categories.id"],
            name="fk_area_conf_comp_category",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "category_confidence_score IS NULL OR "
            "(category_confidence_score >= 0.0000 AND category_confidence_score <= 1.0000)",
            name="chk_area_conf_comp_score",
        ),
        sa.CheckConstraint(
            "report_count >= 0 AND confident_report_count >= 0",
            name="chk_area_conf_comp_counts",
        ),
        sa.CheckConstraint(
            "availability_state IN ('OBSERVED', 'INSUFFICIENT_DATA')",
            name="chk_area_conf_comp_avail",
        ),
        sa.UniqueConstraint(
            "area_confidence_id",
            "category_id",
            name="uq_area_conf_comp_category",
        ),
    )
    op.create_index(
        "idx_area_conf_comp_score_id",
        "area_confidence_components",
        ["area_confidence_id"],
    )

    # 10. Seed baseline duplicate detection configuration
    bind = op.get_bind()
    dup_config_tbl = sa.table(
        "duplicate_detection_configurations",
        sa.column("version", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("spatial_radius_metres", sa.Numeric),
        sa.column("time_window_days", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    bind.execute(
        sa.insert(dup_config_tbl).values(
            version="v1.0.0",
            name="Baseline Proximity Deduplication",
            description=(
                "Proximity candidate detection: 50.0m metric radius, 30 days time window, "
                "same report category, active reports only."
            ),
            spatial_radius_metres=50.00,
            time_window_days=30,
            is_active=True,
        )
    )

    # 11. Seed baseline confidence configuration v1.0.0
    conf_config_tbl = sa.table(
        "confidence_configurations",
        sa.column("id", sa.SmallInteger),
        sa.column("version", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("methodology_metadata", postgresql.JSONB),
    )
    res = bind.execute(
        sa.insert(conf_config_tbl)
        .values(
            version="v1.0.0",
            name="Baseline Evidence Confidence Methodology",
            description=(
                "Transparent multi-factor assessment: verification completeness, "
                "evidence freshness, and independent corroboration. "
                "Missing or deferred factors dynamically re-normalized."
            ),
            is_active=True,
            methodology_metadata={
                "weight_tolerance": 0.0001,
                "scale": "0.0000-1.0000",
                "formula": "normalized_weighted_sum_available",
            },
        )
        .returning(conf_config_tbl.c.id)
    )
    conf_id = res.scalar_one()

    # 12. Seed baseline confidence configuration factors
    factors_tbl = sa.table(
        "confidence_configuration_factors",
        sa.column("configuration_id", sa.SmallInteger),
        sa.column("factor_code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("weight", sa.Numeric),
        sa.column("is_measurable", sa.Boolean),
        sa.column("unavailability_reason", sa.String),
    )
    bind.execute(
        sa.insert(factors_tbl).values(
            [
                {
                    "configuration_id": conf_id,
                    "factor_code": "VERIFICATION_COMPLETENESS",
                    "name": "Verification Completeness",
                    "description": (
                        "Evaluates completeness of inspector verification (severity assigned, "
                        "decision notes, and moderation quality)."
                    ),
                    "weight": 0.3000,
                    "is_measurable": True,
                    "unavailability_reason": None,
                },
                {
                    "configuration_id": conf_id,
                    "factor_code": "EVIDENCE_FRESHNESS",
                    "name": "Evidence Freshness",
                    "description": (
                        "Evaluates observation timeliness (latency between physical observation "
                        "and digital submission)."
                    ),
                    "weight": 0.2500,
                    "is_measurable": True,
                    "unavailability_reason": None,
                },
                {
                    "configuration_id": conf_id,
                    "factor_code": "INDEPENDENT_CORROBORATION",
                    "name": "Independent Corroboration",
                    "description": (
                        "Evaluates whether deficiency observation is corroborated by independent "
                        "reporters in spatial and temporal proximity."
                    ),
                    "weight": 0.2500,
                    "is_measurable": True,
                    "unavailability_reason": None,
                },
                {
                    "configuration_id": conf_id,
                    "factor_code": "EVIDENCE_AVAILABILITY",
                    "name": "Evidence Availability",
                    "description": "Primary photographic evidence attachment availability.",
                    "weight": 0.1000,
                    "is_measurable": False,
                    "unavailability_reason": (
                        "Photographic evidence upload deferred in current system milestone"
                    ),
                },
                {
                    "configuration_id": conf_id,
                    "factor_code": "EVIDENCE_QUALITY",
                    "name": "Evidence Quality",
                    "description": "Photographic resolution, clarity, and metadata integrity.",
                    "weight": 0.1000,
                    "is_measurable": False,
                    "unavailability_reason": (
                        "Photographic evidence upload deferred in current system milestone"
                    ),
                },
            ]
        )
    )


def downgrade() -> None:
    # Drop in reverse topological order
    op.drop_index("idx_area_conf_comp_score_id", table_name="area_confidence_components")
    op.drop_table("area_confidence_components")

    op.drop_index("idx_area_confidence_area_timestamp", table_name="area_confidence_scores")
    op.drop_index("uq_area_confidence_current", table_name="area_confidence_scores")
    op.drop_table("area_confidence_scores")

    op.drop_index("idx_rep_conf_comp_score_id", table_name="report_confidence_components")
    op.drop_table("report_confidence_components")

    op.drop_index("idx_report_conf_report_timestamp", table_name="report_confidence_scores")
    op.drop_index("uq_report_confidence_current", table_name="report_confidence_scores")
    op.drop_table("report_confidence_scores")

    op.drop_table("confidence_configuration_factors")
    op.drop_table("confidence_configurations")

    op.drop_index("idx_dup_history_timestamp", table_name="duplicate_review_history")
    op.drop_index("idx_dup_history_reviewer", table_name="duplicate_review_history")
    op.drop_index("idx_dup_history_canonical_report", table_name="duplicate_review_history")
    op.drop_index("idx_dup_history_duplicate_report", table_name="duplicate_review_history")
    op.drop_table("duplicate_review_history")

    op.drop_index("idx_dup_candidates_status", table_name="duplicate_candidates")
    op.drop_index("idx_dup_candidates_second", table_name="duplicate_candidates")
    op.drop_index("idx_dup_candidates_first", table_name="duplicate_candidates")
    op.drop_table("duplicate_candidates")

    op.drop_table("duplicate_detection_configurations")
