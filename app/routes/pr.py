from fastapi import APIRouter, Request

from app.constants import REPO_ID_SEPARATOR
from app.models import PRReviewRequest, StructuredReviewResponse

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
