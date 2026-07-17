from fastapi import APIRouter, Request

from app.models import PRReviewRequest, StructuredReviewResponse
from app.services.github import PullRequestRef

router = APIRouter(prefix="/review", tags=["review"])


def _build_pr_review_context(pr: PullRequestRef, diff: str) -> str:
    return f"Pull request {pr.owner}/{pr.repo}#{pr.number}:\n\n```diff\n{diff}\n```"


@router.post("/pr", response_model=StructuredReviewResponse)
async def review_pr(request: PRReviewRequest, req: Request) -> StructuredReviewResponse:
    """Fetch a GitHub pull request's diff and run it through the structured reviewer."""
    github_service = req.app.state.github_service
    pr = github_service.parse_pr_url(request.pr_url)
    diff = await github_service.fetch_pr_diff(pr, request.github_token)
    code_context = _build_pr_review_context(pr, diff)

    result = await req.app.state.reviewer.review_structured(
        code=code_context, language="diff"
    )
    return StructuredReviewResponse(
        detected_language=result.detected_language,
        summary=result.summary,
        severity=result.severity,
        score=result.score,
        bugs=result.bugs,
        security_issues=result.security_issues,
        suggestions=result.suggestions,
        positives=result.positives,
    )
