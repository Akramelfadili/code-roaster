"""Add reviews.schema_version.

Revision ID: 897b8a47cbc5
Revises: b7f22987b011
Create Date: 2026-10-12 19:40:00.000000

Existing rows are left NULL on purpose: a result stored before versions
existed reads as "result schema outdated" rather than being assumed current.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "897b8a47cbc5"
down_revision: str | Sequence[str] | None = "b7f22987b011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the version of the shape `reviews.result` was written in."""
    op.add_column("reviews", sa.Column("schema_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Drop `reviews.schema_version`."""
    op.drop_column("reviews", "schema_version")
