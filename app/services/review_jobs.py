"""Create, read, run and stream PR review jobs, persisted in Postgres.

A review job is a `reviews` row plus an append-only log of `review_events`.
`run_review_job` runs as a FastAPI background task: it moves the row through
its states and appends an event at every step. `stream_review_events` polls
that log for the SSE route. Both sides go through Postgres, never process
memory, so a client can follow a job running on another worker, and reconnect
from its last event ID without missing any. The event log is the extension
point for V5: agent steps become new event types.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import (
    INTERNAL_SERVER_ERROR_MESSAGE,
    REVIEW_JOB_ORPHANED_ERROR,
    REVIEW_JOB_TIMEOUT_SECONDS,
    ReviewEventType,
    ReviewJobState,
    ReviewStage,
)
from app.exceptions import AppError, ReviewError
from app.models.db import ReviewEvent, ReviewJob
from app.models.db.review import ACTIVE_REVIEW_JOB_STATES, TERMINAL_REVIEW_EVENT_TYPES
from app.models.review import StructuredReview, StructuredReviewResponse
from app.models.review_job import ReviewEventMessage, ReviewJobStatus
from app.services.github import GitHubService
from app.services.reviewer import CodeReviewer

logger = logging.getLogger(__name__)

# How often an SSE stream checks the event log for new events.
_EVENT_POLL_INTERVAL_SECONDS = 0.5

_STAGE_EVENT_TYPES = {
    ReviewStage.RETRIEVING: ReviewEventType.RETRIEVING,
    ReviewStage.REVIEWING: ReviewEventType.REVIEWING,
}

# An event waiting to be written: its type and its `data` payload.
_NewEvent = tuple[ReviewEventType, dict[str, object] | None]
_StageCallback = Callable[[ReviewStage], Awaitable[None]]


async def create_review_job(
    session: AsyncSession, pr_url: str, repo_id: str | None
) -> ReviewJobStatus:
    """Record a new pending review job for `pr_url`."""
    job = ReviewJob(pr_url=pr_url, repo_id=repo_id, state=ReviewJobState.PENDING)
    session.add(job)
    await session.commit()
    return _to_status(job)


async def get_review_job(session: AsyncSession, job_id: UUID) -> ReviewJobStatus | None:
    """Return the review job with `job_id`, or `None` if there is none."""
    job = await session.get(ReviewJob, job_id)
    return _to_status(job) if job is not None else None


async def fail_orphaned_review_jobs(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[UUID]:
    """Mark jobs left pending/running by a restart as failed; return their IDs.

    Same sweep as `fail_orphaned_indexing_jobs`: only jobs not updated for
    `REVIEW_JOB_TIMEOUT_SECONDS` are swept, so a job still running on another
    worker is left alone. Each swept job also gets its terminal `failed`
    event, so SSE subscribers see it end.
    """
    cutoff = func.now() - timedelta(seconds=REVIEW_JOB_TIMEOUT_SECONDS)
    async with session_factory() as session:
        job_ids = list(
            await session.scalars(
                update(ReviewJob)
                .where(
                    ReviewJob.state.in_(ACTIVE_REVIEW_JOB_STATES),
                    ReviewJob.updated_at < cutoff,
                )
                .values(state=ReviewJobState.FAILED, error=REVIEW_JOB_ORPHANED_ERROR)
                .returning(ReviewJob.id)
            )
        )
        session.add_all(
            _failed_event(job_id, REVIEW_JOB_ORPHANED_ERROR) for job_id in job_ids
        )
        await session.commit()
    return job_ids


async def run_review_job(
    reviewer: CodeReviewer,
    github_service: GitHubService,
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    github_token: str,
) -> None:
    """Review the job's pull request, recording every step as an event.

    Runs after the `202` has been sent, so `main.py`'s exception handlers
    can't catch its failures: it logs them itself and ends the job with a
    `failed` event. It opens its own sessions, since the request's session
    is closed by the time a background task runs.
    """

    async def record_stage(stage: ReviewStage) -> None:
        await _record_events(
            session_factory, job_id, [(_STAGE_EVENT_TYPES[stage], None)]
        )

    try:
        job = await _start_job(session_factory, job_id)
        review = await _review_pr(
            reviewer, github_service, job, github_token, record_stage
        )
    except AppError as e:
        logger.log(
            e.log_level,
            f"Review job {job_id} failed -> {type(e).__name__}: {e}",
            exc_info=e if e.log_level >= logging.ERROR else None,
        )
        await _mark_failed(session_factory, job_id, e.client_message)
        return
    except Exception:
        logger.exception(f"Review job {job_id} failed unexpectedly")
        await _mark_failed(session_factory, job_id, INTERNAL_SERVER_ERROR_MESSAGE)
        return
    await _mark_completed(session_factory, job_id, review)


async def stream_review_events(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    after_event_id: int | None = None,
) -> AsyncIterator[ReviewEventMessage]:
    """Yield the job's events after `after_event_id`, then follow new ones.

    Ends after the terminal `completed`/`failed` event, or straight away if
    the job has already finished and there is nothing newer to send.
    """
    last_event_id = after_event_id or 0
    while True:
        state, events = await _fetch_events_after(
            session_factory, job_id, last_event_id
        )
        for event in events:
            yield event
            if event.type in TERMINAL_REVIEW_EVENT_TYPES:
                return
            last_event_id = event.id
        if state not in ACTIVE_REVIEW_JOB_STATES:
            return
        await asyncio.sleep(_EVENT_POLL_INTERVAL_SECONDS)


async def _review_pr(
    reviewer: CodeReviewer,
    github_service: GitHubService,
    job: ReviewJobStatus,
    github_token: str,
    record_stage: _StageCallback,
) -> StructuredReview:
    """Fetch the job's PR diff with the caller's token and review it.

    The diff fetch comes first, so retrieval from `job.repo_id` only happens
    once the token has proven access to the repo — as in `POST /review/pr`.
    """
    if job.pr_url is None:
        raise ReviewError(f"Review job {job.id} has no pr_url")
    pr = github_service.parse_pr_url(job.pr_url)
    diff = await github_service.fetch_pr_diff(pr, github_token)
    pr_label = f"{pr.owner}/{pr.repo}#{pr.number}"
    if job.repo_id is None:
        await record_stage(ReviewStage.REVIEWING)
        return await reviewer.review_pr_diff(pr_label, diff)
    return await reviewer.review_pr_with_context(
        diff, job.repo_id, pr_label, on_stage=record_stage
    )


async def _start_job(
    session_factory: async_sessionmaker[AsyncSession], job_id: UUID
) -> ReviewJobStatus:
    """Move the job to `running` and return its row."""
    async with session_factory() as session:
        job = await session.scalar(
            update(ReviewJob)
            .where(ReviewJob.id == job_id)
            .values(state=ReviewJobState.RUNNING)
            .returning(ReviewJob)
        )
        await session.commit()
    if job is None:
        raise ReviewError(f"Review job {job_id} disappeared before it started")
    return _to_status(job)


async def _mark_completed(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    review: StructuredReview,
) -> None:
    """Store the result; emit one `finding` event per finding, then `completed`."""
    response = StructuredReviewResponse.from_domain(review)
    result = response.model_dump(mode="json")
    findings = [
        *response.bugs,
        *response.security_issues,
        *response.suggestions,
        *response.positives,
    ]
    events: list[_NewEvent] = [
        (ReviewEventType.FINDING, finding.model_dump(mode="json"))
        for finding in findings
    ]
    events.append((ReviewEventType.COMPLETED, result))
    await _record_events(
        session_factory, job_id, events, state=ReviewJobState.COMPLETED, result=result
    )


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession], job_id: UUID, error: str
) -> None:
    """Record the job's failure and emit its `failed` event."""
    await _record_events(
        session_factory,
        job_id,
        [(ReviewEventType.FAILED, {"error": error})],
        state=ReviewJobState.FAILED,
        error=error,
    )


async def _record_events(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    events: Sequence[_NewEvent],
    **values: object,
) -> None:
    """Append `events` and write `values` to the job's row in one transaction.

    Always bumps `updated_at`, so the orphan sweep measures time since the
    job's last event — a runner that keeps emitting events is never swept.
    """
    async with session_factory() as session:
        await session.execute(
            update(ReviewJob)
            .where(ReviewJob.id == job_id)
            .values(updated_at=func.now(), **values)
        )
        session.add_all(
            ReviewEvent(review_id=job_id, type=event_type, data=data)
            for event_type, data in events
        )
        await session.commit()


async def _fetch_events_after(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    after_event_id: int,
) -> tuple[ReviewJobState | None, list[ReviewEventMessage]]:
    """Return the job's state and its events newer than `after_event_id`.

    The state is read first: a job that finishes in between then still has
    its terminal event in the list, so the stream can't end without it.
    """
    async with session_factory() as session:
        state = await session.scalar(
            select(ReviewJob.state).where(ReviewJob.id == job_id)
        )
        rows = await session.scalars(
            select(ReviewEvent)
            .where(ReviewEvent.review_id == job_id, ReviewEvent.id > after_event_id)
            .order_by(ReviewEvent.id)
        )
        return state, [ReviewEventMessage.model_validate(row) for row in rows]


def _failed_event(job_id: UUID, error: str) -> ReviewEvent:
    """Build a job's terminal `failed` event."""
    return ReviewEvent(
        review_id=job_id, type=ReviewEventType.FAILED, data={"error": error}
    )


def _to_status(job: ReviewJob) -> ReviewJobStatus:
    """Map a `ReviewJob` row to the API's `ReviewJobStatus`."""
    result = None
    if job.result is not None:
        result = StructuredReviewResponse.model_validate(job.result)
    return ReviewJobStatus(
        id=job.id,
        pr_url=job.pr_url,
        repo_id=job.repo_id,
        state=job.state,
        result=result,
        error=job.error,
    )
