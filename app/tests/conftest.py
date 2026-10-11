from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base
from app.main import app
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


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Session factory on a freshly reset test database, set on `app.state`.

    Skips the test when `TEST_DATABASE_URL` is unset. Every table is dropped
    and recreated first, so never point it at a database you care about.
    """
    if settings.test_database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set — see app/claude-docs/testing.md")
    # NullPool: pytest-asyncio gives each test its own event loop, and pooled
    # asyncpg connections can't be reused across loops.
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.session_factory = session_factory
    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    mock_reviewer: MagicMock,
    mock_github_service: MagicMock,
    mock_indexer: MagicMock,
) -> AsyncIterator[AsyncClient]:
    # ASGITransport does not trigger the lifespan, so we set app.state directly.
    app.state.reviewer = mock_reviewer
    app.state.github_service = mock_github_service
    app.state.indexer = mock_indexer
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
