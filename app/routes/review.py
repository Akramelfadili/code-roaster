from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models import ReviewRequest, ReviewResponse, StructuredReviewResponse

router = APIRouter()


@router.post("/review", response_model=ReviewResponse)
async def review_code(request: ReviewRequest, req: Request) -> ReviewResponse:
    review = await req.app.state.reviewer.review(request.code, request.language)
    return ReviewResponse(review=review)


@router.post("/review/stream")
async def review_code_stream(request: ReviewRequest, req: Request) -> StreamingResponse:
    return StreamingResponse(
        req.app.state.reviewer.review_stream(request.code, request.language),
        media_type="text/plain",
    )


@router.post("/review/structured", response_model=StructuredReviewResponse)
async def review_code_structured(
    request: ReviewRequest, req: Request
) -> StructuredReviewResponse:
    result = await req.app.state.reviewer.review_structured(
        code=request.code, language=request.language
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


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
