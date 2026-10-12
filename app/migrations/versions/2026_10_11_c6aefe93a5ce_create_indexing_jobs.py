"""Create the indexing_jobs table.

Revision ID: c6aefe93a5ce
Revises:
Create Date: 2026-10-11 00:00:00.000000

Migrations are frozen snapshots of the schema at the time they were written,
so the enum values below are literals on purpose — importing them from
`app.constants` would silently rewrite history when the constants change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6aefe93a5ce"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXING_JOB_STATE = sa.Enum(
    "pending", "running", "completed", "failed", name="indexing_job_state"
)


def upgrade() -> None:
    """Create `indexing_jobs` with its repo_id and one-active-job-per-repo indexes."""
    op.create_table(
        "indexing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repo_id", sa.String(), nullable=False),
        sa.Column("repo_url", sa.String(), nullable=False),
        sa.Column("state", _INDEXING_JOB_STATE, nullable=False),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("files_processed", sa.Integer(), nullable=True),
        sa.Column("chunks_created", sa.Integer(), nullable=True),
        sa.Column("chunks_stored", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
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
    op.create_index(
        op.f("ix_indexing_jobs_repo_id"), "indexing_jobs", ["repo_id"], unique=False
    )
    op.create_index(
        "uq_indexing_jobs_active_repo_id",
        "indexing_jobs",
        ["repo_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('pending', 'running')"),
    )


def downgrade() -> None:
    """Drop `indexing_jobs` and its enum type."""
    op.drop_index("uq_indexing_jobs_active_repo_id", table_name="indexing_jobs")
    op.drop_index(op.f("ix_indexing_jobs_repo_id"), table_name="indexing_jobs")
    op.drop_table("indexing_jobs")
    _INDEXING_JOB_STATE.drop(op.get_bind(), checkfirst=True)
