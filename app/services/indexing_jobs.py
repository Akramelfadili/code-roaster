"""Create, read and run repository indexing jobs, persisted in Postgres.

Every job's state lives in the `indexing_jobs` table — never in process
memory — so it survives restarts and every worker sees the same jobs.
`create_indexing_job` and `get_latest_indexing_job` serve the `/index`
routes; `fail_orphaned_indexing_jobs` runs at startup; `run_indexing_job`
wraps `RepoIndexer.index_repository` for FastAPI's `BackgroundTasks`, writing
progress and the outcome to the job's row so the status endpoint can report
it.
"""

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import (
    INDEXING_JOB_ORPHANED_ERROR,
    INDEXING_JOB_TIMEOUT_SECONDS,
    INTERNAL_SERVER_ERROR_MESSAGE,
    IndexingJobState,
    IndexingStage,
)
from app.exceptions import (
    AppError,
    IndexingAlreadyInProgressError,
    IndexingJobNotFoundError,
)
from app.models.db import IndexingJob
from app.models.db.indexing import ACTIVE_INDEXING_JOB_STATES
from app.models.index import IndexingJobStatus, IndexingSummary
from app.services.indexer import IndexingResult, RepoIndexer

logger = logging.getLogger(__name__)


async def create_indexing_job(
    session: AsyncSession, repo_id: str, repo_url: str
) -> IndexingJobStatus:
    """Record a new pending job for `repo_id`.

    Raises:
        IndexingAlreadyInProgressError: The repo already has a pending or
            running job — enforced by a partial unique index, so it also
            holds across workers.
    """
    job = IndexingJob(
        repo_id=repo_id, repo_url=repo_url, state=IndexingJobState.PENDING
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise IndexingAlreadyInProgressError(
            f"{repo_id} is already being indexed"
        ) from e
    return _to_status(job)


async def get_latest_indexing_job(
    session: AsyncSession, repo_id: str
) -> IndexingJobStatus:
    """Return the status of `repo_id`'s most recent indexing job.

    Raises:
        IndexingJobNotFoundError: The repo has never been indexed.
    """
    job = await session.scalar(
        select(IndexingJob)
        .where(IndexingJob.repo_id == repo_id)
        .order_by(IndexingJob.created_at.desc())
        .limit(1)
    )
    if job is None:
        raise IndexingJobNotFoundError(f"No indexing job found for {repo_id}")
    return _to_status(job)


async def fail_orphaned_indexing_jobs(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[str]:
    """Mark jobs left pending/running by a restart as failed; return their repo IDs.

    `BackgroundTasks` die with the process, so these rows would otherwise
    stay active forever and block their repo with 409s. Only jobs not updated
    for `INDEXING_JOB_TIMEOUT_SECONDS` are swept, so a job still running on
    another worker is left alone. The cutoff uses the database's clock, the
    same one that stamps `updated_at`.
    """
    cutoff = func.now() - timedelta(seconds=INDEXING_JOB_TIMEOUT_SECONDS)
    async with session_factory() as session:
        repo_ids = await session.scalars(
            update(IndexingJob)
            .where(
                IndexingJob.state.in_(ACTIVE_INDEXING_JOB_STATES),
                IndexingJob.updated_at < cutoff,
            )
            .values(state=IndexingJobState.FAILED, error=INDEXING_JOB_ORPHANED_ERROR)
            .returning(IndexingJob.repo_id)
        )
        orphaned_repo_ids = list(repo_ids)
        await session.commit()
    return orphaned_repo_ids


async def run_indexing_job(
    indexer: RepoIndexer,
    session_factory: async_sessionmaker[AsyncSession],
    job: IndexingJobStatus,
    github_token: str,
) -> None:
    """Index `job`'s repository, recording progress and outcome on its row.

    Like streaming, this runs after the response has been sent, so `main.py`'s
    exception handlers can't catch its failures. It catches and logs them
    itself and records them on the job, which would otherwise stay `running`
    forever. It opens its own sessions: the request's session is closed by
    the time a background task runs.
    """

    async def record_stage(stage: IndexingStage) -> None:
        await _update_job(session_factory, job.id, stage=stage.value)

    try:
        await _update_job(session_factory, job.id, state=IndexingJobState.RUNNING)
        result = await indexer.index_repository(
            job.repo_url, github_token, job.repo_id, on_stage=record_stage
        )
    except AppError as e:
        logger.log(
            e.log_level,
            f"Indexing {job.repo_id} failed -> {type(e).__name__}: {e}",
            exc_info=e if e.log_level >= logging.ERROR else None,
        )
        await _mark_failed(session_factory, job.id, e.client_message)
        return
    except Exception:
        logger.exception(f"Indexing {job.repo_id} failed unexpectedly")
        await _mark_failed(session_factory, job.id, INTERNAL_SERVER_ERROR_MESSAGE)
        return
    await _mark_completed(session_factory, job.id, result)


async def _mark_completed(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    result: IndexingResult,
) -> None:
    """Record a job's success and summary counts, clearing its stage."""
    await _update_job(
        session_factory,
        job_id,
        state=IndexingJobState.COMPLETED,
        stage=None,
        files_processed=result.files_processed,
        chunks_created=result.chunks_created,
        chunks_stored=result.chunks_stored,
        duration_seconds=result.duration_seconds,
    )


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession], job_id: UUID, error: str
) -> None:
    """Record a job's failure, keeping `stage` to show where it stopped."""
    await _update_job(
        session_factory, job_id, state=IndexingJobState.FAILED, error=error
    )


async def _update_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: UUID,
    **values: object,
) -> None:
    """Write `values` to the job's row in a short transaction of its own."""
    async with session_factory() as session:
        await session.execute(
            update(IndexingJob).where(IndexingJob.id == job_id).values(**values)
        )
        await session.commit()


def _to_status(job: IndexingJob) -> IndexingJobStatus:
    """Map an `IndexingJob` row to the API's `IndexingJobStatus`."""
    summary = None
    if job.state is IndexingJobState.COMPLETED:
        summary = IndexingSummary.model_validate(job)
    return IndexingJobStatus(
        id=job.id,
        repo_id=job.repo_id,
        repo_url=job.repo_url,
        state=job.state,
        stage=IndexingStage(job.stage) if job.stage is not None else None,
        summary=summary,
        error=job.error,
    )
