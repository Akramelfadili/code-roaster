from typing import Literal

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    code: str
    language: str = "python"


class ReviewResponse(BaseModel):
    review: str


class StructuredReviewResponse(BaseModel):
    summary: str
    severity: Literal["low", "medium", "high", "critical"]
    score: int = Field(ge=1, le=10)
    bugs: list[str]
    security_issues: list[str]
    suggestions: list[str]
    positives: list[str]
