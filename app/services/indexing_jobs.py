"""Run a repository indexing job in the background and track its status.

`run_indexing_job` wraps `RepoIndexer.index_repository` for FastAPI's
`BackgroundTasks`, recording progress and the outcome on the job's
`IndexingJobStatus` so the status endpoint can report it.
"""

import logging

from app.constants import INTERNAL_SERVER_ERROR_MESSAGE, IndexingJobState
from app.exceptions import AppError
from app.models.index import IndexingJobStatus, IndexingSummary
from app.services.indexer import RepoIndexer

logger = logging.getLogger(__name__)


async def run_indexing_job(
    indexer: RepoIndexer, job: IndexingJobStatus, github_token: str
) -> None:
    """Index `job`'s repository, recording progress and outcome on `job`.

    Like streaming, this runs after the response has been sent, so `main.py`'s
    exception handlers can't catch its failures. It catches and logs them
    itself and records them on the job, which would otherwise stay `running`
    forever.
    """
    job.state = IndexingJobState.RUNNING
    try:
        result = await indexer.index_repository(
            job.repo_url, github_token, job.repo_id, on_stage=job.set_stage
        )
    except AppError as e:
        logger.log(
            e.log_level,
            f"Indexing {job.repo_id} failed -> {type(e).__name__}: {e}",
            exc_info=e if e.log_level >= logging.ERROR else None,
        )
        _mark_failed(job, e.client_message)
        return
    except Exception:
        logger.exception(f"Indexing {job.repo_id} failed unexpectedly")
        _mark_failed(job, INTERNAL_SERVER_ERROR_MESSAGE)
        return
    job.summary = IndexingSummary.model_validate(result)
    job.stage = None
    job.state = IndexingJobState.COMPLETED


def _mark_failed(job: IndexingJobStatus, error: str) -> None:
    """Record a job's failure, keeping `stage` to show where it stopped."""
    job.error = error
    job.state = IndexingJobState.FAILED
