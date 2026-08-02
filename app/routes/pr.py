from fastapi import APIRouter, Request

from app.models import PRReviewRequest, StructuredReviewResponse

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/pr", response_model=StructuredReviewResponse)
async def review_pr(request: PRReviewRequest, req: Request) -> StructuredReviewResponse:
    """Fetch a GitHub pull request's diff and run it through the structured reviewer."""
    github_service = req.app.state.github_service
    pr = github_service.parse_pr_url(request.pr_url)
    diff = await github_service.fetch_pr_diff(pr, request.github_token)
    pr_label = f"{pr.owner}/{pr.repo}#{pr.number}"

    result = await req.app.state.reviewer.review_pr_diff(pr_label, diff)
    return StructuredReviewResponse.from_domain(result)
