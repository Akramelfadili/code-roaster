"""Create the reviews and review_events tables.

Revision ID: c6a346c895d2
Revises: c6aefe93a5ce
Create Date: 2026-10-11 00:00:00.000000

Migrations are frozen snapshots of the schema at the time they were written,
so the enum values below are literals on purpose — importing them from
`app.constants` would silently rewrite history when the constants change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c6a346c895d2"
down_revision: str | Sequence[str] | None = "c6aefe93a5ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_JOB_STATE = sa.Enum(
    "pending", "running", "completed", "failed", name="review_job_state"
)


def upgrade() -> None:
    """Create `reviews` and its append-only `review_events` log."""
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repo_id", sa.String(), nullable=True),
        sa.Column("pr_url", sa.String(), nullable=True),
        sa.Column("state", _REVIEW_JOB_STATE, nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "review_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        # A plain string, not a Postgres enum, so new event types need no migration.
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_events_review_id_id",
        "review_events",
        ["review_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop `review_events`, `reviews` and the review job state enum."""
    op.drop_index("ix_review_events_review_id_id", table_name="review_events")
    op.drop_table("review_events")
    op.drop_table("reviews")
    _REVIEW_JOB_STATE.drop(op.get_bind(), checkfirst=True)
