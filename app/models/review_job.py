from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from app.constants import ReviewEventType, ReviewJobState
from app.models.review import StructuredReviewResponse


class ReviewJobCreated(BaseModel):
    """Body of the `202` returned by `POST /review/pr/async`."""

    job_id: UUID


class ReviewJobStatus(BaseModel):
    """Snapshot of one review job, built from its `ReviewJob` row.

    The row in Postgres is the source of truth; `result` is set only once
    the job has completed.
    """

    id: UUID
    pr_url: str | None
    repo_id: str | None
    state: ReviewJobState
    result: StructuredReviewResponse | None = None
    error: str | None = None


class ReviewEventMessage(BaseModel):
    """One event of a review job's SSE stream, sent as the `data:` JSON.

    `data` by type: `null` for `retrieving` / `reviewing`, a `Finding` for
    `finding`, the full `StructuredReviewResponse` for `completed`, and
    `{"error": ...}` for `failed`. `id` is also the SSE event ID.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ReviewEventType
    data: dict[str, JsonValue] | None = None
