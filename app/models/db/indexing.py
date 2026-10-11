"""The `indexing_jobs` table — one row per repository indexing run."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import IndexingJobState
from app.database import Base

ACTIVE_INDEXING_JOB_STATES = (IndexingJobState.PENDING, IndexingJobState.RUNNING)


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Store a `StrEnum`'s lowercase values in Postgres, not its member names."""
    return [member.value for member in enum_class]


class IndexingJob(Base):
    """One run of the indexing pipeline for a repository.

    A repository keeps one row per (re-)index; the status endpoint reads the
    newest. The summary counts are filled in only once the job completes, and
    `stage` keeps the last pipeline stage entered so a failure shows where it
    stopped.
    """

    __tablename__ = "indexing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[str] = mapped_column(index=True)
    repo_url: Mapped[str]
    state: Mapped[IndexingJobState] = mapped_column(
        Enum(
            IndexingJobState,
            name="indexing_job_state",
            values_callable=_enum_values,
        ),
        default=IndexingJobState.PENDING,
    )
    stage: Mapped[str | None]
    files_processed: Mapped[int | None]
    chunks_created: Mapped[int | None]
    chunks_stored: Mapped[int | None]
    duration_seconds: Mapped[float | None]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# At most one pending or running job per repository. Enforced by Postgres
# rather than a check in the route, so two workers racing on the same repo
# can't both start it — the loser's INSERT fails with an IntegrityError.
Index(
    "uq_indexing_jobs_active_repo_id",
    IndexingJob.repo_id,
    unique=True,
    postgresql_where=IndexingJob.state.in_(ACTIVE_INDEXING_JOB_STATES),
)
