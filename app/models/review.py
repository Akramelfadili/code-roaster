from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReviewRequest(BaseModel):
    code: str
    language: str = "python"

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Code must not be empty")
        return v


class ReviewResponse(BaseModel):
    review: str


class StructuredReviewResponse(BaseModel):
    detected_language: str
    summary: str
    severity: Literal["low", "medium", "high", "critical"]
    score: int = Field(ge=1, le=10)
    bugs: list[str]
    security_issues: list[str]
    suggestions: list[str]
    positives: list[str]
