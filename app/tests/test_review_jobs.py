import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import (
    REVIEW_JOB_ORPHANED_ERROR,
    REVIEW_JOB_TIMEOUT_SECONDS,
    ReviewEventType,
    ReviewJobState,
)
from app.models.db import ReviewEvent, ReviewJob
from app.services import review_jobs
from app.services.review_jobs import fail_orphaned_review_jobs, stream_review_events
from app.tests.mocks import SAMPLE_PR_URL, SAMPLE_REPO_ID

_PAST_TIMEOUT = timedelta(seconds=REVIEW_JOB_TIMEOUT_SECONDS + 60)
_WITHIN_TIMEOUT = timedelta(seconds=REVIEW_JOB_TIMEOUT_SECONDS - 60)
_FAST_POLL_INTERVAL_SECONDS = 0.01


async def _add_job(
    session_factory: async_sessionmaker[AsyncSession],
    state: ReviewJobState,
    last_updated_ago: timedelta = timedelta(0),
) -> UUID:
    job = ReviewJob(
        pr_url=SAMPLE_PR_URL,
        repo_id=SAMPLE_REPO_ID,
        state=state,
        updated_at=func.now() - last_updated_ago,
    )
    async with session_factory() as session:
        session.add(job)
        await session.commit()
    return job.id


async def _add_event(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    event_type: ReviewEventType,
    state: ReviewJobState | None = None,
) -> None:
    async with session_factory() as session:
        session.add(ReviewEvent(review_id=job_id, type=event_type))
        if state is not None:
            job = await session.get(ReviewJob, job_id)
            assert job is not None
            job.state = state
        await session.commit()


async def _get_job(
    session_factory: async_sessionmaker[AsyncSession], job_id: UUID
) -> ReviewJob:
    async with session_factory() as session:
        job = await session.get(ReviewJob, job_id)
    assert job is not None
    return job


async def _event_types(
    session_factory: async_sessionmaker[AsyncSession], job_id: UUID
) -> list[ReviewEventType]:
    async with session_factory() as session:
        types = await session.scalars(
            select(ReviewEvent.type)
            .where(ReviewEvent.review_id == job_id)
            .order_by(ReviewEvent.id)
        )
        return list(types)


async def _collect_types(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    after_event_id: int | None = None,
) -> list[ReviewEventType]:
    return [
        event.type
        async for event in stream_review_events(session_factory, job_id, after_event_id)
    ]


class TestFailOrphanedReviewJobs:
    @pytest.mark.parametrize("state", [ReviewJobState.PENDING, ReviewJobState.RUNNING])
    async def test_stale_active_job_is_failed_with_failed_event(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        state: ReviewJobState,
    ) -> None:
        job_id = await _add_job(db_session_factory, state, _PAST_TIMEOUT)

        orphaned_job_ids = await fail_orphaned_review_jobs(db_session_factory)

        job = await _get_job(db_session_factory, job_id)
        assert orphaned_job_ids == [job_id]
        assert job.state is ReviewJobState.FAILED
        assert job.error == REVIEW_JOB_ORPHANED_ERROR
        assert await _event_types(db_session_factory, job_id) == [
            ReviewEventType.FAILED
        ]

    async def test_recently_updated_running_job_is_left_running(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        job_id = await _add_job(
            db_session_factory, ReviewJobState.RUNNING, _WITHIN_TIMEOUT
        )

        orphaned_job_ids = await fail_orphaned_review_jobs(db_session_factory)

        job = await _get_job(db_session_factory, job_id)
        assert orphaned_job_ids == []
        assert job.state is ReviewJobState.RUNNING
        assert await _event_types(db_session_factory, job_id) == []

    async def test_stale_completed_job_is_left_completed(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        job_id = await _add_job(
            db_session_factory, ReviewJobState.COMPLETED, _PAST_TIMEOUT
        )

        orphaned_job_ids = await fail_orphaned_review_jobs(db_session_factory)

        assert orphaned_job_ids == []
        job = await _get_job(db_session_factory, job_id)
        assert job.state is ReviewJobState.COMPLETED


class TestStreamReviewEvents:
    async def test_follows_running_job_until_terminal_event(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            review_jobs, "_EVENT_POLL_INTERVAL_SECONDS", _FAST_POLL_INTERVAL_SECONDS
        )
        job_id = await _add_job(db_session_factory, ReviewJobState.RUNNING)
        stream = asyncio.create_task(_collect_types(db_session_factory, job_id))

        await _add_event(db_session_factory, job_id, ReviewEventType.REVIEWING)
        await _add_event(
            db_session_factory,
            job_id,
            ReviewEventType.COMPLETED,
            state=ReviewJobState.COMPLETED,
        )

        assert await asyncio.wait_for(stream, timeout=5) == [
            ReviewEventType.REVIEWING,
            ReviewEventType.COMPLETED,
        ]

    async def test_finished_job_with_nothing_newer_ends_immediately(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        job_id = await _add_job(db_session_factory, ReviewJobState.RUNNING)
        await _add_event(
            db_session_factory,
            job_id,
            ReviewEventType.FAILED,
            state=ReviewJobState.FAILED,
        )
        async with db_session_factory() as session:
            last_event_id = await session.scalar(select(func.max(ReviewEvent.id)))

        assert await _collect_types(db_session_factory, job_id, last_event_id) == []
