from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest

from app.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    MalformedAIResponseError,
)
from app.services.chunker import Chunk
from app.services.embedder import Embedder
from app.services.reviewer import CodeReviewer
from app.services.vector_store import VectorStore
from app.tests.mocks import SAMPLE_CHUNK, SAMPLE_CODE, SAMPLE_REPO_ID

_ANTHROPIC_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
_SAMPLE_TOOL_OUTPUT = {
    "detected_language": "Python",
    "summary": "Clean, readable function with no major issues.",
    "severity": "low",
    "score": 8,
    "bugs": [],
    "security_issues": [],
    "suggestions": ["Consider adding a docstring"],
    "positives": ["Good use of type hints"],
}


def _rate_limit_error() -> anthropic.RateLimitError:
    response = httpx.Response(429, request=_ANTHROPIC_REQUEST, json={})
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def _api_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(
        message="connection failed", request=_ANTHROPIC_REQUEST
    )


def _make_response(content: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(
        content=content, usage=SimpleNamespace(input_tokens=10, output_tokens=20)
    )


class _FakeMessageStream:
    def __init__(self, chunks: list[str], usage: SimpleNamespace) -> None:
        self.text_stream = self._iter_chunks(chunks)
        self._usage = usage

    async def _iter_chunks(self, chunks: list[str]) -> Any:
        for chunk in chunks:
            yield chunk

    async def __aenter__(self) -> "_FakeMessageStream":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get_final_message(self) -> SimpleNamespace:
        return SimpleNamespace(usage=self._usage)


class TestBuildReviewMessage:
    def test_auto_language_asks_to_detect_language(self) -> None:
        reviewer = CodeReviewer(client=MagicMock())
        message = reviewer._build_review_message(SAMPLE_CODE, "auto")
        assert "detect the language automatically" in message
        assert SAMPLE_CODE in message

    def test_explicit_language_is_named_in_message(self) -> None:
        reviewer = CodeReviewer(client=MagicMock())
        message = reviewer._build_review_message(SAMPLE_CODE, "python")
        assert "Review this python code" in message
        assert SAMPLE_CODE in message


class TestReviewStructured:
    async def test_happy_path_returns_structured_review(self) -> None:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        reviewer = CodeReviewer(client=mock_client)

        review = await reviewer.review_structured(SAMPLE_CODE, "python")

        assert review.detected_language == "Python"
        assert review.severity == "low"
        assert review.score == 8

    async def test_rate_limit_error_raises_ai_provider_rate_limit_error(self) -> None:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=_rate_limit_error())
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(AIProviderRateLimitError):
            await reviewer.review_structured(SAMPLE_CODE, "python")

    async def test_api_error_raises_ai_provider_error(self) -> None:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=_api_error())
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(AIProviderError):
            await reviewer.review_structured(SAMPLE_CODE, "python")

    async def test_missing_tool_use_block_raises_malformed_response(self) -> None:
        mock_client = MagicMock()
        text_block = SimpleNamespace(type="text", text="not a tool call")
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([text_block])
        )
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(MalformedAIResponseError):
            await reviewer.review_structured(SAMPLE_CODE, "python")

    async def test_missing_required_field_raises_malformed_response(self) -> None:
        mock_client = MagicMock()
        incomplete_output = {
            k: v for k, v in _SAMPLE_TOOL_OUTPUT.items() if k != "score"
        }
        tool_use_block = SimpleNamespace(type="tool_use", input=incomplete_output)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(MalformedAIResponseError):
            await reviewer.review_structured(SAMPLE_CODE, "python")


class TestReviewPrDiff:
    async def test_wraps_diff_and_delegates_to_review_structured(self) -> None:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        reviewer = CodeReviewer(client=mock_client)

        await reviewer.review_pr_diff("octocat/hello-world#42", "diff --git a/f b/f")

        sent_message = mock_client.messages.create.call_args.kwargs["messages"][0]
        assert "octocat/hello-world#42" in sent_message["content"]
        assert "diff --git a/f b/f" in sent_message["content"]


class TestReviewPrWithContext:
    _PR_LABEL = "octocat/hello-world#42"
    _DIFF = "diff --git a/f b/f"

    def _make_reviewer(
        self, collection_exists: bool, chunks: list[Chunk]
    ) -> tuple[CodeReviewer, MagicMock, MagicMock, MagicMock]:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        vector_store = MagicMock(spec=VectorStore)
        vector_store.collection_exists.return_value = collection_exists
        vector_store.search.return_value = chunks
        vector_store_factory = MagicMock(return_value=vector_store)
        embedder = MagicMock(spec=Embedder)
        embedder.embed_query = AsyncMock(return_value=[0.1, 0.2])
        reviewer = CodeReviewer(
            client=mock_client,
            embedder=embedder,
            vector_store_factory=vector_store_factory,
        )
        return reviewer, mock_client, vector_store, embedder

    async def test_injects_retrieved_chunks_before_diff(self) -> None:
        reviewer, mock_client, vector_store, embedder = self._make_reviewer(
            collection_exists=True, chunks=[SAMPLE_CHUNK]
        )

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL
        )

        embedder.embed_query.assert_awaited_once_with(self._DIFF)
        vector_store.search.assert_awaited_once_with([0.1, 0.2], 5)
        reviewer.vector_store_factory.assert_called_once_with(SAMPLE_REPO_ID)  # type: ignore[attr-defined]
        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "File: app/helpers.py (lines 10-11)" in content
        assert SAMPLE_CHUNK.content in content
        assert content.index(SAMPLE_CHUNK.content) < content.index(self._DIFF)
        assert self._PR_LABEL in content

    async def test_missing_index_falls_back_to_plain_diff_review(self) -> None:
        reviewer, mock_client, vector_store, embedder = self._make_reviewer(
            collection_exists=False, chunks=[SAMPLE_CHUNK]
        )

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL
        )

        embedder.embed_query.assert_not_awaited()
        vector_store.search.assert_not_awaited()
        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert self._DIFF in content
        assert "Relevant context" not in content

    async def test_empty_search_results_fall_back_to_plain_diff_review(self) -> None:
        reviewer, mock_client, vector_store, _ = self._make_reviewer(
            collection_exists=True, chunks=[]
        )

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL
        )

        vector_store.search.assert_awaited_once()
        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert self._DIFF in content
        assert "Relevant context" not in content


class TestReviewStream:
    async def test_happy_path_yields_stream_text(self) -> None:
        mock_client = MagicMock()
        usage = SimpleNamespace(input_tokens=5, output_tokens=15)
        mock_client.messages.stream = MagicMock(
            return_value=_FakeMessageStream(["Streaming ", "review"], usage)
        )
        reviewer = CodeReviewer(client=mock_client)

        chunks = [
            chunk async for chunk in reviewer.review_stream(SAMPLE_CODE, "python")
        ]

        assert chunks == ["Streaming ", "review"]

    async def test_rate_limit_error_raises_ai_provider_rate_limit_error(self) -> None:
        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=_rate_limit_error())
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(AIProviderRateLimitError):
            async for _ in reviewer.review_stream(SAMPLE_CODE, "python"):
                pass

    async def test_api_error_raises_ai_provider_error(self) -> None:
        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(side_effect=_api_error())
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(AIProviderError):
            async for _ in reviewer.review_stream(SAMPLE_CODE, "python"):
                pass
