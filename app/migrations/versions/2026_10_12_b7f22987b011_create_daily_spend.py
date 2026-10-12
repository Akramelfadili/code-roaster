"""Create the daily_spend table.

Revision ID: b7f22987b011
Revises: c6a346c895d2
Create Date: 2026-10-12 19:20:45.158203
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f22987b011"
down_revision: str | Sequence[str] | None = "c6a346c895d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create `daily_spend`, one row of AI spend per UTC day."""
    op.create_table(
        "daily_spend",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "spent_usd",
            sa.Numeric(precision=12, scale=6),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("day"),
    )


def downgrade() -> None:
    """Drop `daily_spend`."""
    op.drop_table("daily_spend")
