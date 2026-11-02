"""SDI intelligence engine architecture and baseline scoring configuration.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02 03:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASELINE_WEIGHTS = [
    ("STREET_LIGHTING", 0.3000),
    ("PEDESTRIAN_PATHWAYS", 0.2500),
    ("VISIBILITY", 0.1500),
    ("PUBLIC_ASSISTANCE", 0.2000),
    ("MAINTENANCE", 0.1000),
]


def upgrade() -> None:
    # 1. Create scoring_configurations table
    op.create_table(
        "scoring_configurations",
        sa.Column(
            "id",
            sa.SmallInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
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
        sa.UniqueConstraint("version", name="uq_scoring_configurations_version"),
    )

    # 2. Create scoring_configuration_weights table
    op.create_table(
        "scoring_configuration_weights",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("configuration_id", sa.SmallInteger(), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["report_categories.id"],
            name="fk_scoring_weights_category",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["scoring_configurations.id"],
            name="fk_scoring_weights_configuration",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "weight >= 0.0000 AND weight <= 1.0000",
            name="chk_config_weight_bounds",
        ),
        sa.UniqueConstraint(
            "configuration_id",
            "category_id",
            name="uq_config_category",
        ),
    )

    # 3. Create area_scores table
    op.create_table(
        "area_scores",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("administrative_area_id", sa.UUID(), nullable=False),
        sa.Column("configuration_id", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("completeness_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("participating_categories_count", sa.SmallInteger(), nullable=False),
        sa.Column("total_categories_count", sa.SmallInteger(), nullable=False),
        sa.Column("eligible_reports_count", sa.Integer(), nullable=False),
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
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "methodology_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["administrative_area_id"],
            ["administrative_areas.id"],
            name="fk_area_scores_administrative_area",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["scoring_configurations.id"],
            name="fk_area_scores_configuration",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0.00 AND score <= 100.00)",
            name="chk_area_scores_score_bounds",
        ),
        sa.CheckConstraint(
            "completeness_pct >= 0.00 AND completeness_pct <= 100.00",
            name="chk_area_scores_completeness_bounds",
        ),
        sa.CheckConstraint(
            "participating_categories_count >= 0 AND total_categories_count > 0 "
            "AND eligible_reports_count >= 0",
            name="chk_area_scores_counts_positive",
        ),
    )

    # Area scores indexes
    op.create_index(
        "uq_area_scores_current",
        "area_scores",
        ["administrative_area_id", "configuration_id"],
        unique=True,
        postgresql_where=sa.text("is_current = True"),
    )
    op.create_index(
        "idx_area_scores_area_timestamp",
        "area_scores",
        ["administrative_area_id", sa.text("calculation_timestamp DESC")],
    )

    # 4. Create score_components table
    op.create_table(
        "score_components",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("area_score_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("category_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("assigned_weight", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("normalized_weight", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("weighted_contribution", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("availability_state", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["area_score_id"],
            ["area_scores.id"],
            name="fk_score_components_area_score",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["report_categories.id"],
            name="fk_score_components_category",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "category_score IS NULL OR (category_score >= 0.00 AND category_score <= 100.00)",
            name="chk_score_components_category_score",
        ),
        sa.CheckConstraint(
            "assigned_weight >= 0.0000 AND assigned_weight <= 1.0000",
            name="chk_score_components_assigned_weight",
        ),
        sa.CheckConstraint(
            "normalized_weight IS NULL OR "
            "(normalized_weight >= 0.0000 AND normalized_weight <= 1.0000)",
            name="chk_score_components_normalized_weight",
        ),
        sa.CheckConstraint(
            "availability_state IN ('OBSERVED', 'INSUFFICIENT_DATA')",
            name="chk_score_components_availability",
        ),
        sa.CheckConstraint(
            "report_count >= 0",
            name="chk_score_components_report_count",
        ),
        sa.UniqueConstraint(
            "area_score_id",
            "category_id",
            name="uq_score_component_area_category",
        ),
    )
    op.create_index(
        "idx_score_components_area_score_id",
        "score_components",
        ["area_score_id"],
    )

    # 5. Seed baseline scoring configuration v1.0.0
    bind = op.get_bind()
    scoring_configs = sa.table(
        "scoring_configurations",
        sa.column("id", sa.SmallInteger),
        sa.column("version", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("methodology_metadata", postgresql.JSONB),
    )

    config_metadata = {
        "min_observations_per_category": 1,
        "severity_scale_max": 5,
        "weight_tolerance": 0.0001,
    }

    result = bind.execute(
        sa.insert(scoring_configs)
        .values(
            version="v1.0.0",
            name="Baseline Infrastructure SDI Methodology",
            description=(
                "Baseline versioned methodology weighting 5 primary deficiency "
                "categories totaling 1.00."
            ),
            is_active=True,
            methodology_metadata=config_metadata,
        )
        .returning(scoring_configs.c.id)
    )
    config_id = result.scalar_one()

    # Retrieve category IDs from report_categories
    categories_tbl = sa.table(
        "report_categories",
        sa.column("id", sa.SmallInteger),
        sa.column("code", sa.String),
    )
    cats = bind.execute(sa.select(categories_tbl.c.id, categories_tbl.c.code)).all()
    cat_map = {code: cid for cid, code in cats}

    weights_tbl = sa.table(
        "scoring_configuration_weights",
        sa.column("configuration_id", sa.SmallInteger),
        sa.column("category_id", sa.SmallInteger),
        sa.column("weight", sa.Numeric),
    )

    weight_inserts = []
    for cat_code, weight in BASELINE_WEIGHTS:
        if cat_code in cat_map:
            weight_inserts.append(
                {
                    "configuration_id": config_id,
                    "category_id": cat_map[cat_code],
                    "weight": weight,
                }
            )

    if weight_inserts:
        bind.execute(sa.insert(weights_tbl).values(weight_inserts))


def downgrade() -> None:
    # Drop tables in reverse topological order
    op.drop_index(
        "idx_score_components_area_score_id",
        table_name="score_components",
    )
    op.drop_table("score_components")

    op.drop_index("idx_area_scores_area_timestamp", table_name="area_scores")
    op.drop_index("uq_area_scores_current", table_name="area_scores")
    op.drop_table("area_scores")

    op.drop_table("scoring_configuration_weights")
    op.drop_table("scoring_configurations")
