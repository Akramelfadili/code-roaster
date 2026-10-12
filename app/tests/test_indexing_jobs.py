from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import (
    INDEXING_JOB_ORPHANED_ERROR,
    INDEXING_JOB_TIMEOUT_SECONDS,
    IndexingJobState,
)
from app.models.db import IndexingJob
from app.services.indexing_jobs import fail_orphaned_indexing_jobs
from app.tests.mocks import SAMPLE_REPO_URL

_PAST_TIMEOUT = timedelta(seconds=INDEXING_JOB_TIMEOUT_SECONDS + 60)
_WITHIN_TIMEOUT = timedelta(seconds=INDEXING_JOB_TIMEOUT_SECONDS - 60)


async def _add_job(
    session_factory: async_sessionmaker[AsyncSession],
    repo_id: str,
    state: IndexingJobState,
    last_updated_ago: timedelta,
) -> None:
    async with session_factory() as session:
        session.add(
            IndexingJob(
                repo_id=repo_id,
                repo_url=SAMPLE_REPO_URL,
                state=state,
                updated_at=func.now() - last_updated_ago,
            )
        )
        await session.commit()


async def _get_job(
    session_factory: async_sessionmaker[AsyncSession], repo_id: str
) -> IndexingJob:
    async with session_factory() as session:
        job = await session.scalar(
            select(IndexingJob).where(IndexingJob.repo_id == repo_id)
        )
    assert job is not None
    return job


class TestFailOrphanedIndexingJobs:
    @pytest.mark.parametrize(
        "state", [IndexingJobState.PENDING, IndexingJobState.RUNNING]
    )
    async def test_stale_active_job_is_marked_failed(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        state: IndexingJobState,
    ) -> None:
        await _add_job(db_session_factory, "o__stale", state, _PAST_TIMEOUT)

        orphaned_repo_ids = await fail_orphaned_indexing_jobs(db_session_factory)

        job = await _get_job(db_session_factory, "o__stale")
        assert orphaned_repo_ids == ["o__stale"]
        assert job.state is IndexingJobState.FAILED
        assert job.error == INDEXING_JOB_ORPHANED_ERROR

    async def test_recently_updated_running_job_is_left_running(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _add_job(
            db_session_factory, "o__live", IndexingJobState.RUNNING, _WITHIN_TIMEOUT
        )

        orphaned_repo_ids = await fail_orphaned_indexing_jobs(db_session_factory)

        job = await _get_job(db_session_factory, "o__live")
        assert orphaned_repo_ids == []
        assert job.state is IndexingJobState.RUNNING
        assert job.error is None

    async def test_stale_completed_job_is_left_completed(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _add_job(
            db_session_factory, "o__done", IndexingJobState.COMPLETED, _PAST_TIMEOUT
        )

        orphaned_repo_ids = await fail_orphaned_indexing_jobs(db_session_factory)

        job = await _get_job(db_session_factory, "o__done")
        assert orphaned_repo_ids == []
        assert job.state is IndexingJobState.COMPLETED
