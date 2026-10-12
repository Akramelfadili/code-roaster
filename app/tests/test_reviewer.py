from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import anthropic
import httpx
import pytest

from app.constants import MAX_CONTEXT_CHARS, ReviewStage
from app.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    MalformedAIResponseError,
    OutputTruncatedError,
)
from app.models.review import Confidence, FindingCategory, StructuredReview
from app.services.chunker import Chunk
from app.services.retriever import CodeRetriever
from app.services.reviewer import CodeReviewer, _fit_context_budget
from app.tests.mocks import SAMPLE_CHUNK, SAMPLE_CODE, SAMPLE_REPO_ID

_ANTHROPIC_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
_SAMPLE_TOOL_OUTPUT = {
    "detected_language": "Python",
    "summary": "Clean, readable function with no major issues.",
    "severity": "low",
    "score": 8,
    "bugs": [
        {
            "title": "Off-by-one in loop",
            "explanation": "The loop skips the last element.",
            "severity": "high",
            "file": "app/main.py",
            "line_start": 12,
            "line_end": 14,
            "suggestion": "Iterate up to len(items) inclusive of the last index.",
            "confidence": "high",
        }
    ],
    "security_issues": [],
    "suggestions": [
        {
            "title": "Missing docstring",
            "explanation": "The function's purpose isn't documented.",
            "severity": "low",
            "confidence": "medium",
        }
    ],
    "positives": [
        {
            "title": "Good use of type hints",
            "explanation": "Parameters and return value are fully annotated.",
            "confidence": "high",
        }
    ],
}


def _rate_limit_error() -> anthropic.RateLimitError:
    response = httpx.Response(429, request=_ANTHROPIC_REQUEST, json={})
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def _api_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(
        message="connection failed", request=_ANTHROPIC_REQUEST
    )


def _make_usage(input_tokens: int, output_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _make_response(
    content: list[Any], stop_reason: str = "tool_use"
) -> SimpleNamespace:
    return SimpleNamespace(
        content=content, usage=_make_usage(10, 20), stop_reason=stop_reason
    )


class _FakeMessageStream:
    def __init__(
        self, chunks: list[str], usage: SimpleNamespace, stop_reason: str = "end_turn"
    ) -> None:
        self.text_stream = self._iter_chunks(chunks)
        self._usage = usage
        self._stop_reason = stop_reason

    async def _iter_chunks(self, chunks: list[str]) -> Any:
        for chunk in chunks:
            yield chunk

    async def __aenter__(self) -> "_FakeMessageStream":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get_final_message(self) -> SimpleNamespace:
        return SimpleNamespace(usage=self._usage, stop_reason=self._stop_reason)


async def _review_with_tool_output(tool_output: dict[str, Any]) -> StructuredReview:
    mock_client = MagicMock()
    tool_use_block = SimpleNamespace(type="tool_use", input=tool_output)
    mock_client.messages.create = AsyncMock(
        return_value=_make_response([tool_use_block])
    )
    reviewer = CodeReviewer(client=mock_client)
    return await reviewer.review_structured(SAMPLE_CODE, "python")


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

    async def test_max_tokens_stop_reason_raises_output_truncated(self) -> None:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block], stop_reason="max_tokens")
        )
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(OutputTruncatedError):
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

    async def test_findings_are_tagged_with_their_list_category(self) -> None:
        review = await _review_with_tool_output(_SAMPLE_TOOL_OUTPUT)

        assert [f.category for f in review.bugs] == [FindingCategory.BUG]
        assert [f.category for f in review.suggestions] == [FindingCategory.SUGGESTION]
        assert [f.category for f in review.positives] == [FindingCategory.POSITIVE]

    async def test_findings_keep_location_and_detail_fields(self) -> None:
        review = await _review_with_tool_output(_SAMPLE_TOOL_OUTPUT)

        bug = review.bugs[0]
        assert bug.title == "Off-by-one in loop"
        assert bug.severity == "high"
        assert (bug.file, bug.line_start, bug.line_end) == ("app/main.py", 12, 14)
        assert bug.confidence == Confidence.HIGH
        assert bug.suggestion is not None

    async def test_optional_finding_fields_default_to_none(self) -> None:
        review = await _review_with_tool_output(_SAMPLE_TOOL_OUTPUT)

        positive = review.positives[0]
        assert positive.severity is None
        assert positive.file is None
        assert positive.line_start is None
        assert positive.suggestion is None

    async def test_each_finding_gets_a_unique_uuid(self) -> None:
        review = await _review_with_tool_output(_SAMPLE_TOOL_OUTPUT)

        ids = [f.id for f in review.bugs + review.suggestions + review.positives]
        assert len(set(ids)) == len(ids)
        for finding_id in ids:
            UUID(finding_id)

    async def test_tool_supplied_id_and_category_are_ignored(self) -> None:
        finding = {
            **_SAMPLE_TOOL_OUTPUT["positives"][0],  # type: ignore[index]
            "id": "model-chosen-id",
            "category": "bug",
        }
        output = {**_SAMPLE_TOOL_OUTPUT, "positives": [finding]}

        review = await _review_with_tool_output(output)

        positive = review.positives[0]
        assert positive.id != "model-chosen-id"
        assert positive.category == FindingCategory.POSITIVE

    async def test_omitted_finding_lists_default_to_empty(self) -> None:
        output = {k: v for k, v in _SAMPLE_TOOL_OUTPUT.items() if k != "bugs"}

        review = await _review_with_tool_output(output)

        assert review.bugs == []

    async def test_finding_missing_required_field_raises_malformed_response(
        self,
    ) -> None:
        invalid_finding = {"title": "No explanation", "confidence": "high"}
        output = {**_SAMPLE_TOOL_OUTPUT, "bugs": [invalid_finding]}

        with pytest.raises(MalformedAIResponseError):
            await _review_with_tool_output(output)

    async def test_plain_string_finding_raises_malformed_response(self) -> None:
        output = {**_SAMPLE_TOOL_OUTPUT, "suggestions": ["Add a docstring"]}

        with pytest.raises(MalformedAIResponseError):
            await _review_with_tool_output(output)


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
        self, chunks: list[Chunk]
    ) -> tuple[CodeReviewer, MagicMock, MagicMock]:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        retriever = MagicMock(spec=CodeRetriever)
        retriever.retrieve = AsyncMock(return_value=chunks)
        reviewer = CodeReviewer(client=mock_client, retriever=retriever)
        return reviewer, mock_client, retriever

    async def test_injects_retrieved_chunks_before_diff(self) -> None:
        reviewer, mock_client, retriever = self._make_reviewer(chunks=[SAMPLE_CHUNK])

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL
        )

        retriever.retrieve.assert_awaited_once_with(SAMPLE_REPO_ID, self._DIFF)
        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "File: app/helpers.py (lines 10-11)" in content
        assert SAMPLE_CHUNK.content in content
        assert content.index(SAMPLE_CHUNK.content) < content.index(self._DIFF)
        assert self._PR_LABEL in content

    async def test_no_retrieved_chunks_falls_back_to_plain_diff_review(
        self,
    ) -> None:
        reviewer, mock_client, retriever = self._make_reviewer(chunks=[])

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL
        )

        retriever.retrieve.assert_awaited_once()
        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert self._DIFF in content
        assert "Relevant context" not in content

    async def test_no_retriever_falls_back_to_plain_diff_review(self) -> None:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        reviewer = CodeReviewer(client=mock_client)

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL
        )

        content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert self._DIFF in content
        assert "Relevant context" not in content

    async def test_reports_retrieving_then_reviewing_stage(self) -> None:
        reviewer, _, _ = self._make_reviewer(chunks=[SAMPLE_CHUNK])
        on_stage = AsyncMock()

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL, on_stage=on_stage
        )

        stages = [call.args[0] for call in on_stage.await_args_list]
        assert stages == [ReviewStage.RETRIEVING, ReviewStage.REVIEWING]

    async def test_no_retriever_reports_only_reviewing_stage(self) -> None:
        mock_client = MagicMock()
        tool_use_block = SimpleNamespace(type="tool_use", input=_SAMPLE_TOOL_OUTPUT)
        mock_client.messages.create = AsyncMock(
            return_value=_make_response([tool_use_block])
        )
        reviewer = CodeReviewer(client=mock_client)
        on_stage = AsyncMock()

        await reviewer.review_pr_with_context(
            self._DIFF, SAMPLE_REPO_ID, self._PR_LABEL, on_stage=on_stage
        )

        on_stage.assert_awaited_once_with(ReviewStage.REVIEWING)


class TestFitContextBudget:
    # Each chunk's formatted size is just over a third of the budget, so only
    # the first two fit.
    _CHUNK_CONTENT_CHARS = MAX_CONTEXT_CHARS // 3

    def _make_ranked_chunks(self, count: int) -> list[Chunk]:
        return [
            Chunk(
                content="x" * self._CHUNK_CONTENT_CHARS,
                file_path=f"rank_{rank}.py",
                start_line=1,
                end_line=2,
                language="python",
            )
            for rank in range(count)
        ]

    def test_over_budget_drops_lowest_ranked_chunks_first(self) -> None:
        chunks = self._make_ranked_chunks(4)

        assert _fit_context_budget(chunks) == chunks[:2]

    def test_within_budget_keeps_every_chunk(self) -> None:
        chunks = self._make_ranked_chunks(2)

        assert _fit_context_budget(chunks) == chunks


class TestReviewStream:
    async def test_happy_path_yields_stream_text(self) -> None:
        mock_client = MagicMock()
        usage = _make_usage(5, 15)
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

    async def test_max_tokens_stop_reason_raises_output_truncated(self) -> None:
        mock_client = MagicMock()
        usage = _make_usage(5, 15)
        mock_client.messages.stream = MagicMock(
            return_value=_FakeMessageStream(["Partial "], usage, "max_tokens")
        )
        reviewer = CodeReviewer(client=mock_client)

        with pytest.raises(OutputTruncatedError):
            async for _ in reviewer.review_stream(SAMPLE_CODE, "python"):
                pass
