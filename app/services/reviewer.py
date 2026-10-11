import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import cast

import anthropic
from anthropic import APIError
from anthropic.types import Usage
from pydantic import ValidationError

from app.config import settings
from app.constants import (
    ANTHROPIC_CACHE_READ_COST_PER_MTOK_USD,
    ANTHROPIC_CACHE_WRITE_COST_PER_MTOK_USD,
    ANTHROPIC_INPUT_COST_PER_MTOK_USD,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_OUTPUT_COST_PER_MTOK_USD,
    MAX_CONTEXT_CHARS,
    TOKENS_PER_MTOK,
    ReviewStage,
)
from app.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    MalformedAIResponseError,
)
from app.models.review import Finding, FindingCategory, StructuredReview
from app.prompts.review import (
    SECURITY_REVIEW_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_TOOL,
    FindingToolOutput,
    ReviewToolOutput,
)
from app.services.chunker import Chunk
from app.services.retriever import CodeRetriever

logger = logging.getLogger(__name__)

_AUTO_LANGUAGE = "auto"
# STRUCTURED_REVIEW_TOOL marks bugs/security_issues/suggestions/positives as
# required too, but Claude has been observed to omit them despite that, so
# they're deliberately excluded here and defaulted via `.get(..., [])` below
# instead of raising. TODO: decide whether to loosen the schema to match this
# (needs a live test against the real API to see if that changes compliance,
# rather than guessing) — see conversation from 2026-07-28.
_REQUIRED_REVIEW_FIELDS = ("summary", "severity", "score", "detected_language")
# Finding fields the server always sets itself; dropped from tool input even if
# Claude volunteers them, so they can never come from the model.
_SERVER_SET_FINDING_FIELDS = frozenset({"id", "category"})
_CONTEXT_CHUNK_SEPARATOR = "\n\n"


async def _ignore_stage(_stage: ReviewStage) -> None:
    """Default `on_stage`: progress reporting is optional."""


def _format_chunk(chunk: Chunk) -> str:
    return (
        f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
        f"```{chunk.language}\n{chunk.content}\n```"
    )


def _fit_context_budget(chunks: list[Chunk]) -> list[Chunk]:
    """Keep the highest-ranked chunks whose formatted context fits the budget.

    `chunks` arrive most relevant first, so the lowest-ranked ones are dropped
    first once the joined context would exceed `MAX_CONTEXT_CHARS`.
    """
    kept: list[Chunk] = []
    context_chars = 0
    for chunk in chunks:
        separator_chars = len(_CONTEXT_CHUNK_SEPARATOR) if kept else 0
        chunk_chars = len(_format_chunk(chunk)) + separator_chars
        if context_chars + chunk_chars > MAX_CONTEXT_CHARS:
            break
        kept.append(chunk)
        context_chars += chunk_chars
    if len(kept) < len(chunks):
        logger.warning(
            f"Dropped {len(chunks) - len(kept)} of {len(chunks)} retrieved chunks "
            f"to fit the {MAX_CONTEXT_CHARS}-char context budget"
        )
    return kept


def _estimate_cost_usd(usage: Usage) -> float:
    """Approximate a Claude call's cost in USD from its token usage."""
    cache_write_tokens = usage.cache_creation_input_tokens or 0
    cache_read_tokens = usage.cache_read_input_tokens or 0
    cost_per_mtok = (
        usage.input_tokens * ANTHROPIC_INPUT_COST_PER_MTOK_USD
        + usage.output_tokens * ANTHROPIC_OUTPUT_COST_PER_MTOK_USD
        + cache_write_tokens * ANTHROPIC_CACHE_WRITE_COST_PER_MTOK_USD
        + cache_read_tokens * ANTHROPIC_CACHE_READ_COST_PER_MTOK_USD
    )
    return cost_per_mtok / TOKENS_PER_MTOK


def _log_usage(call_type: str, usage: Usage) -> None:
    """Log one Claude call's token usage and its approximate cost."""
    logger.info(
        f"Token usage — type={call_type} input={usage.input_tokens} "
        f"output={usage.output_tokens} cost_usd={_estimate_cost_usd(usage):.4f}"
    )


def _require_review_fields(data: ReviewToolOutput) -> None:
    missing = [field for field in _REQUIRED_REVIEW_FIELDS if field not in data]
    if missing:
        raise MalformedAIResponseError(
            f"Tool response missing required fields: {', '.join(missing)}"
        )


def _to_finding(item: FindingToolOutput, category: FindingCategory) -> Finding:
    """Validate one raw tool finding, tagging it with its list's category."""
    # The tool input is the model's JSON, so the TypedDict shape isn't guaranteed:
    # a plain string here would otherwise escape as a TypeError.
    if not isinstance(item, dict):
        raise MalformedAIResponseError(
            "Tool response finding is not an object", debug_context=repr(item)
        )
    model_fields = {
        key: value
        for key, value in item.items()
        if key not in _SERVER_SET_FINDING_FIELDS
    }
    return Finding.model_validate({**model_fields, "category": category})


def _to_findings(
    items: list[FindingToolOutput], category: FindingCategory
) -> list[Finding]:
    """Validate the tool's raw findings, tagging each with its list's category."""
    return [_to_finding(item, category) for item in items]


def _build_structured_review(data: ReviewToolOutput) -> StructuredReview:
    """Turn validated tool output into the domain review.

    Raises:
        MalformedAIResponseError: If any finding fails `Finding` validation.
    """
    try:
        return StructuredReview(
            detected_language=data["detected_language"],
            summary=data["summary"],
            severity=data["severity"],
            score=data["score"],
            bugs=_to_findings(data.get("bugs", []), FindingCategory.BUG),
            security_issues=_to_findings(
                data.get("security_issues", []), FindingCategory.SECURITY
            ),
            suggestions=_to_findings(
                data.get("suggestions", []), FindingCategory.SUGGESTION
            ),
            positives=_to_findings(data.get("positives", []), FindingCategory.POSITIVE),
        )
    except ValidationError as e:
        raise MalformedAIResponseError(
            "Tool response contains an invalid finding", debug_context=str(e)
        ) from e


class CodeReviewer:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        retriever: CodeRetriever | None = None,
    ) -> None:
        """Create a reviewer.

        Args:
            client: Anthropic async client. Defaults to one authenticated with
                ``settings.anthropic_api_key``; pass a fake in tests.
            retriever: Supplies codebase context for PR reviews. Without one,
                `review_pr_with_context` reviews the diff alone.
        """
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
        self.model = ANTHROPIC_MODEL
        self.retriever = retriever

    def _build_review_message(self, code: str, language: str) -> str:
        if language == _AUTO_LANGUAGE:
            return (
                "Review this code (detect the language automatically):"
                f"\n\n```\n{code}\n```"
            )
        return f"Review this {language} code:\n\n```{language}\n{code}\n```"

    async def review_structured(
        self, code: str, language: str = "python"
    ) -> StructuredReview:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": STRUCTURED_REVIEW_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[STRUCTURED_REVIEW_TOOL],
                tool_choice={"type": "tool", "name": "submit_code_review"},
                messages=[
                    {
                        "role": "user",
                        "content": self._build_review_message(code, language),
                    }
                ],
            )
        except anthropic.RateLimitError as e:
            raise AIProviderRateLimitError("Anthropic API rate limit exceeded") from e
        except APIError as e:
            raise AIProviderError("Anthropic API call failed") from e

        _log_usage("structured", response.usage)

        tool_use_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise MalformedAIResponseError("No tool_use block in response")
        data = cast(ReviewToolOutput, tool_use_block.input)
        _require_review_fields(data)
        return _build_structured_review(data)

    async def review_pr_diff(self, pr_label: str, diff: str) -> StructuredReview:
        """Review a GitHub PR's diff, labeled for context (e.g. "owner/repo#1")."""
        code_context = f"Pull request {pr_label}:\n\n```diff\n{diff}\n```"
        return await self.review_structured(code=code_context, language="diff")

    async def review_pr_with_context(
        self,
        diff: str,
        repo_id: str,
        pr_label: str,
        on_stage: Callable[[ReviewStage], Awaitable[None]] | None = None,
    ) -> StructuredReview:
        """Review a PR diff augmented with the most relevant indexed codebase chunks.

        `repo_id` must be derived server-side from a PR the caller can access,
        never taken from client input, or the review can leak another repo's code.
        Falls back to a plain `review_pr_diff` when there is no retriever or it
        finds no chunks. Retrieval itself is delegated to `CodeRetriever`.
        Retrieved context is capped at `MAX_CONTEXT_CHARS`, dropping the
        lowest-ranked chunks first.

        Args:
            on_stage: Awaited as each `ReviewStage` starts, to report progress
                (review jobs turn it into SSE events). `retrieving` is skipped
                when there is no retriever.
        """
        report_stage = on_stage or _ignore_stage
        if self.retriever is None:
            await report_stage(ReviewStage.REVIEWING)
            return await self.review_pr_diff(pr_label, diff)

        await report_stage(ReviewStage.RETRIEVING)
        chunks = await self.retriever.retrieve(repo_id, diff)
        await report_stage(ReviewStage.REVIEWING)
        chunks = _fit_context_budget(chunks)
        if not chunks:
            return await self.review_pr_diff(pr_label, diff)

        context = _CONTEXT_CHUNK_SEPARATOR.join(
            _format_chunk(chunk) for chunk in chunks
        )
        code_context = (
            f"Relevant context from the existing codebase:\n\n{context}\n\n"
            f"Pull request {pr_label}:\n\n```diff\n{diff}\n```"
        )
        return await self.review_structured(code=code_context, language="diff")

    async def review_stream(
        self, code: str, language: str = "python"
    ) -> AsyncIterator[str]:
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": SECURITY_REVIEW_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": self._build_review_message(code, language),
                    }
                ],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final_message = await stream.get_final_message()
                _log_usage("stream", final_message.usage)
        except anthropic.RateLimitError as e:
            # The client's exception handler can't cleanly turn this into a JSON
            # error response once streaming has started sending bytes, so log
            # here with full context rather than relying on main.py to do it.
            logger.warning(f"Anthropic API rate limit exceeded mid-stream: {e}")
            raise AIProviderRateLimitError("Anthropic API rate limit exceeded") from e
        except APIError as e:
            logger.error(f"Anthropic API call failed mid-stream: {e}", exc_info=e)
            raise AIProviderError("Anthropic API call failed") from e
