from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.constants import IndexingJobState, IndexingStage


class IndexRepoRequest(BaseModel):
    repo_url: str
    github_token: str

    @field_validator("repo_url")
    @classmethod
    def repo_url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("repo_url must not be empty")
        return v

    @field_validator("github_token")
    @classmethod
    def github_token_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("github_token must not be empty")
        return v


class IndexingSummary(BaseModel):
    """Counts and timing from a completed indexing run.

    Built from the service's `IndexingResult` dataclass via `from_attributes`,
    so this module doesn't import `app.services` (which imports `app.models`).
    """

    model_config = ConfigDict(from_attributes=True)

    files_processed: int
    chunks_created: int
    chunks_stored: int
    duration_seconds: float


class IndexingJobStatus(BaseModel):
    """Status of one repository indexing job, as returned by the `/index` routes.

    Built from an `IndexingJob` row by `app/services/indexing_jobs.py`; the
    row in Postgres is the source of truth, this is a read-only snapshot.
    """

    id: UUID
    repo_id: str
    repo_url: str
    state: IndexingJobState = IndexingJobState.PENDING
    stage: IndexingStage | None = None
    summary: IndexingSummary | None = None
    error: str | None = None
