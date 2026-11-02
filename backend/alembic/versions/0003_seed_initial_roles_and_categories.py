"""Seed initial roles and report categories.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-02 02:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES_DATA = [
    {
        "name": "citizen",
        "description": "Citizen reporting public-space infrastructure deficiencies.",
    },
    {
        "name": "verifier",
        "description": (
            "Authorized personnel and field inspectors reviewing and verifying submitted reports."
        ),
    },
    {
        "name": "maintenance",
        "description": (
            "Municipal maintenance personnel and contractors assigned to address verified issues."
        ),
    },
    {
        "name": "admin",
        "description": (
            "System administrators managing user accounts, jurisdictions, and system configuration."
        ),
    },
]

CATEGORIES_DATA = [
    {
        "code": "STREET_LIGHTING",
        "name": "Street Lighting",
        "description": (
            "Poor or non-functional street lighting, dark corridors, broken luminaires, "
            "or unlit public pathways."
        ),
        "is_active": True,
    },
    {
        "code": "PEDESTRIAN_PATHWAYS",
        "name": "Pedestrian Pathways",
        "description": (
            "Damaged pedestrian pathways, fractured sidewalks, missing curb ramps, "
            "hazardous surface obstructions, or broken walkways."
        ),
        "is_active": True,
    },
    {
        "code": "VISIBILITY",
        "name": "Visibility and Sightlines",
        "description": (
            "Obstructed public-space visibility, overgrown vegetation, blind corners, "
            "concealed alcoves, or missing safety mirrors."
        ),
        "is_active": True,
    },
    {
        "code": "PUBLIC_ASSISTANCE",
        "name": "Public Assistance Facilities",
        "description": (
            "Missing or damaged public assistance facilities, non-functional emergency call boxes, "
            "absent aid signage, or lack of emergency help points."
        ),
        "is_active": True,
    },
    {
        "code": "MAINTENANCE",
        "name": "Public Space Maintenance",
        "description": (
            "Poor public-space maintenance, broken street furniture, open drainage, "
            "hazardous littering, accumulation of waste, or vandalized public facilities."
        ),
        "is_active": True,
    },
]


def upgrade() -> None:
    """Insert baseline standard roles and category taxonomy into database."""
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(roles_table, ROLES_DATA)

    categories_table = sa.table(
        "report_categories",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(categories_table, CATEGORIES_DATA)


def downgrade() -> None:
    """Remove baseline seed data for report categories and roles.

    Respects existing foreign-key restrictions (ON DELETE RESTRICT); fails safely
    without deleting dependent application records if seeded records are referenced.
    """
    op.execute(
        "DELETE FROM report_categories WHERE code IN ("
        "'STREET_LIGHTING', 'PEDESTRIAN_PATHWAYS', 'VISIBILITY', "
        "'PUBLIC_ASSISTANCE', 'MAINTENANCE')"
    )
    op.execute("DELETE FROM roles WHERE name IN ('citizen', 'verifier', 'maintenance', 'admin')")
