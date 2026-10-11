from fastapi import APIRouter, BackgroundTasks, Request, status

from app.constants import REPO_ID_SEPARATOR
from app.exceptions import IndexingAlreadyInProgressError, IndexingJobNotFoundError
from app.models import IndexingJobStatus, IndexRepoRequest
from app.services.indexing_jobs import run_indexing_job

router = APIRouter(prefix="/index", tags=["index"])


@router.post(
    "/repo", response_model=IndexingJobStatus, status_code=status.HTTP_202_ACCEPTED
)
async def index_repo(
    request: IndexRepoRequest, req: Request, background_tasks: BackgroundTasks
) -> IndexingJobStatus:
    """Start indexing a repository in the background; poll its status by `repo_id`."""
    owner, repo = req.app.state.github_service.parse_repo_url(request.repo_url)
    repo_id = f"{owner}{REPO_ID_SEPARATOR}{repo}".lower()
    jobs: dict[str, IndexingJobStatus] = req.app.state.indexing_jobs

    existing_job = jobs.get(repo_id)
    if existing_job is not None and existing_job.is_active:
        raise IndexingAlreadyInProgressError(f"{repo_id} is already being indexed")

    job = IndexingJobStatus(repo_id=repo_id, repo_url=request.repo_url)
    jobs[repo_id] = job
    background_tasks.add_task(
        run_indexing_job, req.app.state.indexer, job, request.github_token
    )
    return job


@router.get("/status/{repo_id}", response_model=IndexingJobStatus)
async def get_index_status(repo_id: str, req: Request) -> IndexingJobStatus:
    """Return the latest status of a repository's indexing job."""
    job: IndexingJobStatus | None = req.app.state.indexing_jobs.get(repo_id)
    if job is None:
        raise IndexingJobNotFoundError(f"No indexing job found for {repo_id}")
    return job
