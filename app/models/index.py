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
    """Live status of one repository's background indexing job.

    Held in `app.state.indexing_jobs` and mutated in place by the job runner
    as it progresses, so polling the status endpoint sees the latest state.
    """

    repo_id: str
    repo_url: str
    state: IndexingJobState = IndexingJobState.PENDING
    stage: IndexingStage | None = None
    summary: IndexingSummary | None = None
    error: str | None = None

    @property
    def is_active(self) -> bool:
        """Whether the job is still queued or running."""
        return self.state in (IndexingJobState.PENDING, IndexingJobState.RUNNING)

    def set_stage(self, stage: IndexingStage) -> None:
        """Record the pipeline stage the job has just entered."""
        self.stage = stage
