from pydantic import BaseModel, field_validator


class PRReviewRequest(BaseModel):
    pr_url: str
    github_token: str

    @field_validator("pr_url")
    @classmethod
    def pr_url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("pr_url must not be empty")
        return v

    @field_validator("github_token")
    @classmethod
    def github_token_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("github_token must not be empty")
        return v
