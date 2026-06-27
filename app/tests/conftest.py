from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.reviewer import CodeReviewer
from app.tests.mocks import SAMPLE_STRUCTURED_REVIEW


@pytest.fixture
def mock_reviewer() -> MagicMock:
    reviewer = MagicMock(spec=CodeReviewer)
    reviewer.review = AsyncMock(return_value="Looks good. No major issues found.")
    reviewer.review_structured = AsyncMock(return_value=SAMPLE_STRUCTURED_REVIEW)

    async def default_stream(code: str, language: str = "python") -> AsyncIterator[str]:
        yield "Streaming "
        yield "review content"

    reviewer.review_stream = MagicMock(side_effect=default_stream)
    return reviewer


@pytest_asyncio.fixture
async def client(mock_reviewer: MagicMock) -> AsyncIterator[AsyncClient]:
    # ASGITransport does not trigger the lifespan, so we set app.state directly.
    app.state.reviewer = mock_reviewer
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
