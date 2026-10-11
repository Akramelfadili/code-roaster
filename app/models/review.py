from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.constants import Severity


class FindingCategory(StrEnum):
    """Which review section a finding belongs to."""

    BUG = "bug"
    SECURITY = "security"
    SUGGESTION = "suggestion"
    POSITIVE = "positive"


class Confidence(StrEnum):
    """How sure the reviewer is that a finding is correct."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Finding(BaseModel):
    """One review finding, located in the code when the reviewer can pin it down.

    `id` is generated server-side, so each finding has a stable handle that
    agents, PR comments, and evals can refer to. `severity` is left unset for
    positives; `file` and the line range are unset when the finding isn't tied
    to a specific location.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    category: FindingCategory
    severity: Severity | None = None
    file: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    title: str
    explanation: str
    suggestion: str | None = None
    confidence: Confidence


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
    bugs: list[Finding]
    security_issues: list[Finding]
    suggestions: list[Finding]
    positives: list[Finding]

    @classmethod
    def from_domain(cls, review: "StructuredReview") -> Self:
        return cls(
            detected_language=review.detected_language,
            summary=review.summary,
            severity=review.severity,
            score=review.score,
            bugs=review.bugs,
            security_issues=review.security_issues,
            suggestions=review.suggestions,
            positives=review.positives,
        )


class StructuredReview:
    """Domain result of an AI code review, as produced by `CodeReviewer`."""

    def __init__(
        self,
        detected_language: str,
        summary: str,
        severity: Severity,
        score: int,
        bugs: list[Finding],
        security_issues: list[Finding],
        suggestions: list[Finding],
        positives: list[Finding],
    ) -> None:
        self.detected_language = detected_language
        self.summary = summary
        self.severity = severity
        self.score = score
        self.bugs = bugs
        self.security_issues = security_issues
        self.suggestions = suggestions
        self.positives = positives
