from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import IndexingJobStatus
from app.services.github import GitHubService
from app.services.indexer import RepoIndexer
from app.services.reviewer import CodeReviewer
from app.tests.mocks import (
    SAMPLE_INDEXING_RESULT,
    SAMPLE_PR_DIFF,
    SAMPLE_PR_REF,
    SAMPLE_REPO_REF,
    SAMPLE_STRUCTURED_REVIEW,
)


@pytest.fixture
def mock_reviewer() -> MagicMock:
    reviewer = MagicMock(spec=CodeReviewer)
    reviewer.review_structured = AsyncMock(return_value=SAMPLE_STRUCTURED_REVIEW)
    reviewer.review_pr_diff = AsyncMock(return_value=SAMPLE_STRUCTURED_REVIEW)
    reviewer.review_pr_with_context = AsyncMock(return_value=SAMPLE_STRUCTURED_REVIEW)

    async def default_stream(code: str, language: str = "python") -> AsyncIterator[str]:
        yield "Streaming "
        yield "review content"

    reviewer.review_stream = MagicMock(side_effect=default_stream)
    return reviewer


@pytest.fixture
def mock_github_service() -> MagicMock:
    service = MagicMock(spec=GitHubService)
    service.client_id = "mock-client-id"
    service.parse_pr_url = MagicMock(return_value=SAMPLE_PR_REF)
    service.fetch_pr_diff = AsyncMock(return_value=SAMPLE_PR_DIFF)
    service.exchange_code_for_token = AsyncMock(return_value="mock-access-token")
    service.parse_repo_url = MagicMock(return_value=SAMPLE_REPO_REF)
    return service


@pytest.fixture
def mock_indexer() -> MagicMock:
    indexer = MagicMock(spec=RepoIndexer)
    indexer.index_repository = AsyncMock(return_value=SAMPLE_INDEXING_RESULT)
    return indexer


@pytest.fixture
def indexing_jobs() -> dict[str, IndexingJobStatus]:
    return {}


@pytest_asyncio.fixture
async def client(
    mock_reviewer: MagicMock,
    mock_github_service: MagicMock,
    mock_indexer: MagicMock,
    indexing_jobs: dict[str, IndexingJobStatus],
) -> AsyncIterator[AsyncClient]:
    # ASGITransport does not trigger the lifespan, so we set app.state directly.
    app.state.reviewer = mock_reviewer
    app.state.github_service = mock_github_service
    app.state.indexer = mock_indexer
    app.state.indexing_jobs = indexing_jobs
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
