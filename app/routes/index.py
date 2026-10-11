from fastapi import APIRouter, BackgroundTasks, Request, status

from app.constants import REPO_ID_SEPARATOR
from app.database import DbSession
from app.models import IndexingJobStatus, IndexRepoRequest
from app.services.indexing_jobs import (
    create_indexing_job,
    get_latest_indexing_job,
    run_indexing_job,
)

router = APIRouter(prefix="/index", tags=["index"])


@router.post(
    "/repo", response_model=IndexingJobStatus, status_code=status.HTTP_202_ACCEPTED
)
async def index_repo(
    request: IndexRepoRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> IndexingJobStatus:
    """Start indexing a repository in the background; poll its status by `repo_id`."""
    owner, repo = req.app.state.github_service.parse_repo_url(request.repo_url)
    repo_id = f"{owner}{REPO_ID_SEPARATOR}{repo}".lower()
    job = await create_indexing_job(db, repo_id, request.repo_url)
    background_tasks.add_task(
        run_indexing_job,
        req.app.state.indexer,
        req.app.state.session_factory,
        job,
        request.github_token,
    )
    return job


@router.get("/status/{repo_id}", response_model=IndexingJobStatus)
async def get_index_status(repo_id: str, db: DbSession) -> IndexingJobStatus:
    """Return the latest status of a repository's indexing job."""
    return await get_latest_indexing_job(db, repo_id)
