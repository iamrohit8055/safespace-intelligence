"""Enable PostGIS extension.

Revision ID: 0001_enable_postgis
Revises:
Create Date: 2026-11-01 22:50:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_enable_postgis"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable PostGIS extension in PostgreSQL."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")


def downgrade() -> None:
    """Preserve PostGIS extension during downgrade.

    The PostGIS extension is intentionally preserved on downgrade to prevent
    cascading data loss or breaking dependent spatial objects and extensions.
    """
    pass
