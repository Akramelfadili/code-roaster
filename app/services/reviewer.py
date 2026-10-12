"""Orchestrate code reviews.

`CodeReviewer` builds the review prompt and wires the pieces together:
`ContextBuilder` supplies codebase context for PR reviews, `ClaudeClient`
makes the call, and `ReviewParser` turns the tool output into a
`StructuredReview`. It makes no API call and parses nothing itself.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import anthropic

from app.constants import ReviewStage
from app.models.review import StructuredReview
from app.prompts.review import (
    SECURITY_REVIEW_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_TOOL,
)
from app.services.claude_client import ClaudeClient
from app.services.context_builder import ContextBuilder
from app.services.cost_budget import CostBudget
from app.services.retriever import CodeRetriever
from app.services.review_parser import ReviewParser

_AUTO_LANGUAGE = "auto"
_STRUCTURED_CALL_TYPE = "structured"
_STREAM_CALL_TYPE = "stream"


async def _ignore_stage(_stage: ReviewStage) -> None:
    """Default `on_stage`: progress reporting is optional."""


class CodeReviewer:
    """Reviews pasted code and PR diffs, streamed or as a `StructuredReview`."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        retriever: CodeRetriever | None = None,
        budget: CostBudget | None = None,
    ) -> None:
        """Create a reviewer.

        Args:
            client: Anthropic async client. Defaults to one authenticated with
                ``settings.anthropic_api_key``; pass a fake in tests.
            retriever: Supplies codebase context for PR reviews. Without one,
                `review_pr_with_context` reviews the diff alone.
            budget: Checked before and charged after every Claude call. Only
                tests leave it out, which disables enforcement.
        """
        self._claude = ClaudeClient(client=client, budget=budget)
        self._parser = ReviewParser()
        self._context_builder = (
            ContextBuilder(retriever) if retriever is not None else None
        )

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
        """Review `code` with a forced `submit_code_review` tool call."""
        tool_input = await self._claude.call_tool(
            system_prompt=STRUCTURED_REVIEW_SYSTEM_PROMPT,
            tool=STRUCTURED_REVIEW_TOOL,
            user_message=self._build_review_message(code, language),
            call_type=_STRUCTURED_CALL_TYPE,
        )
        return self._parser.parse(tool_input)

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
        Falls back to a plain `review_pr_diff` when there is no retriever or no
        context fits. Context comes from `ContextBuilder`, capped at
        `MAX_CONTEXT_CHARS` with the lowest-ranked chunks dropped first.

        Args:
            on_stage: Awaited as each `ReviewStage` starts, to report progress
                (review jobs turn it into SSE events). `retrieving` is skipped
                when there is no retriever.
        """
        report_stage = on_stage or _ignore_stage
        if self._context_builder is None:
            await report_stage(ReviewStage.REVIEWING)
            return await self.review_pr_diff(pr_label, diff)

        await report_stage(ReviewStage.RETRIEVING)
        context = await self._context_builder.build(repo_id, diff)
        await report_stage(ReviewStage.REVIEWING)
        if context is None:
            return await self.review_pr_diff(pr_label, diff)

        code_context = (
            f"Relevant context from the existing codebase:\n\n{context}\n\n"
            f"Pull request {pr_label}:\n\n```diff\n{diff}\n```"
        )
        return await self.review_structured(code=code_context, language="diff")

    async def review_stream(
        self, code: str, language: str = "python"
    ) -> AsyncIterator[str]:
        """Stream a prose review of `code` as Claude writes it."""
        async for text in self._claude.stream_text(
            system_prompt=SECURITY_REVIEW_SYSTEM_PROMPT,
            user_message=self._build_review_message(code, language),
            call_type=_STREAM_CALL_TYPE,
        ):
            yield text
