from pydantic import BaseModel, Field, field_validator

from app.constants import Severity


class ReviewRequest(BaseModel):
    code: str
    language: str = "python"

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Code must not be empty")
        return v


class StructuredReviewResponse(BaseModel):
    detected_language: str
    summary: str
    severity: Severity
    score: int = Field(ge=1, le=10)
    bugs: list[str]
    security_issues: list[str]
    suggestions: list[str]
    positives: list[str]


class StructuredReview:
    """Domain result of an AI code review, as produced by `CodeReviewer`."""

    def __init__(
        self,
        detected_language: str,
        summary: str,
        severity: Severity,
        score: int,
        bugs: list[str],
        security_issues: list[str],
        suggestions: list[str],
        positives: list[str],
    ) -> None:
        self.detected_language = detected_language
        self.summary = summary
        self.severity = severity
        self.score = score
        self.bugs = bugs
        self.security_issues = security_issues
        self.suggestions = suggestions
        self.positives = positives
