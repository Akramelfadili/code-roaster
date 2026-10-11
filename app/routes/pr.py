from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.constants import REPO_ID_SEPARATOR
from app.database import DbSession, FunctionScopedDbSession
from app.exceptions import ReviewJobNotFoundError
from app.models import (
    PRReviewRequest,
    ReviewJobCreated,
    ReviewJobStatus,
    StructuredReviewResponse,
)
from app.services.review_jobs import (
    create_review_job,
    get_review_job,
    run_review_job,
    stream_review_events,
)

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/pr", response_model=StructuredReviewResponse)
async def review_pr(request: PRReviewRequest, req: Request) -> StructuredReviewResponse:
    """Fetch a GitHub pull request's diff and review it with its repo's indexed context.

    The `repo_id` is derived from the PR itself, only after the diff fetch proves
    the caller's token can access the repo, so clients can't pull in another
    repo's indexed code.
    """
    github_service = req.app.state.github_service
    pr = github_service.parse_pr_url(request.pr_url)
    diff = await github_service.fetch_pr_diff(pr, request.github_token)
    pr_label = f"{pr.owner}/{pr.repo}#{pr.number}"
    repo_id = f"{pr.owner}{REPO_ID_SEPARATOR}{pr.repo}".lower()

    result = await req.app.state.reviewer.review_pr_with_context(
        diff, repo_id, pr_label
    )
    return StructuredReviewResponse.from_domain(result)


@router.post(
    "/pr/async", response_model=ReviewJobCreated, status_code=status.HTTP_202_ACCEPTED
)
async def review_pr_async(
    request: PRReviewRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> ReviewJobCreated:
    """Start reviewing a pull request in the background; follow it over SSE.

    The `repo_id` is derived from the PR URL, never from the client. The job
    fetches the diff with the caller's token before it retrieves any context,
    so it only reaches a repo's indexed code once the token has proven access.
    """
    github_service = req.app.state.github_service
    pr = github_service.parse_pr_url(request.pr_url)
    repo_id = f"{pr.owner}{REPO_ID_SEPARATOR}{pr.repo}".lower()
    job = await create_review_job(db, request.pr_url, repo_id)
    background_tasks.add_task(
        run_review_job,
        req.app.state.reviewer,
        github_service,
        req.app.state.session_factory,
        job.id,
        request.github_token,
    )
    return ReviewJobCreated(job_id=job.id)


async def _require_review_job(
    job_id: UUID, db: FunctionScopedDbSession
) -> ReviewJobStatus:
    """Resolve `job_id` to its job before the stream starts, so a miss is a 404."""
    job = await get_review_job(db, job_id)
    if job is None:
        raise ReviewJobNotFoundError(f"No review job found with id {job_id}")
    return job


@router.get("/pr/{job_id}/events", response_class=EventSourceResponse)
async def stream_review_job_events(
    job: Annotated[ReviewJobStatus, Depends(_require_review_job, scope="function")],
    req: Request,
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterator[ServerSentEvent]:
    """Stream a review job's events over SSE, ending after `completed` or `failed`.

    Replays every event first, so a late subscriber misses nothing; a
    reconnecting `EventSource` resumes after its `Last-Event-ID`.
    """
    session_factory = req.app.state.session_factory
    async for event in stream_review_events(session_factory, job.id, last_event_id):
        yield ServerSentEvent(data=event, id=str(event.id))
