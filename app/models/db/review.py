"""The `reviews` and `review_events` tables — review jobs and their event log."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import ReviewEventType, ReviewJobState
from app.database import Base, enum_values

ACTIVE_REVIEW_JOB_STATES = (ReviewJobState.PENDING, ReviewJobState.RUNNING)
TERMINAL_REVIEW_EVENT_TYPES = (ReviewEventType.COMPLETED, ReviewEventType.FAILED)

_EVENT_TYPE_MAX_LENGTH = 32


class ReviewJob(Base):
    """One background review run.

    `result` holds the full `StructuredReviewResponse` JSON once the job
    completes, and `schema_version` the version of that shape it was written
    in (`REVIEW_RESULT_SCHEMA_VERSION`), so a read can tell an outdated result
    from a current one. `repo_id` is set for PR reviews that pull in RAG context.
    """

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[str | None]
    pr_url: Mapped[str | None]
    state: Mapped[ReviewJobState] = mapped_column(
        Enum(ReviewJobState, name="review_job_state", values_callable=enum_values),
        default=ReviewJobState.PENDING,
    )
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    schema_version: Mapped[int | None]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReviewEvent(Base):
    """One event a review job emitted, replayed to its SSE subscribers.

    `id` is a global sequence: it orders a job's events and is the SSE event
    ID a reconnecting client resumes from (`Last-Event-ID`). `type` is a
    plain string column rather than a Postgres enum, so adding an event type
    (V5 agent steps) needs no migration.
    """

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE")
    )
    type: Mapped[ReviewEventType] = mapped_column(
        Enum(
            ReviewEventType,
            native_enum=False,
            length=_EVENT_TYPE_MAX_LENGTH,
            values_callable=enum_values,
        )
    )
    data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# The SSE stream's only query: one job's events after a given ID, in order.
Index("ix_review_events_review_id_id", ReviewEvent.review_id, ReviewEvent.id)
