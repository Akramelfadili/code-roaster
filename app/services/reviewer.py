import os
from collections.abc import AsyncIterator
from typing import cast

import anthropic
from anthropic import APIError

from app.exceptions import AIProviderError, MalformedAIResponseError
from app.models.review import StructuredReview
from app.prompts.review import (
    SECURITY_REVIEW_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_SYSTEM_PROMPT,
    STRUCTURED_REVIEW_TOOL,
    ReviewToolOutput,
)

_AUTO_LANGUAGE = "auto"
# STRUCTURED_REVIEW_TOOL marks bugs/security_issues/suggestions/positives as
# required too, but Claude has been observed to omit them despite that, so
# they're deliberately excluded here and defaulted via `.get(..., [])` below
# instead of raising. TODO: decide whether to loosen the schema to match this
# (needs a live test against the real API to see if that changes compliance,
# rather than guessing) — see conversation from 2026-07-28.
_REQUIRED_REVIEW_FIELDS = ("summary", "severity", "score", "detected_language")


def _require_review_fields(data: ReviewToolOutput) -> None:
    missing = [field for field in _REQUIRED_REVIEW_FIELDS if field not in data]
    if missing:
        raise MalformedAIResponseError(
            f"Tool response missing required fields: {', '.join(missing)}"
        )


class CodeReviewer:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = "claude-sonnet-4-6"

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
                max_tokens=2048,
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
        except APIError as e:
            raise AIProviderError("Anthropic API call failed") from e

        tool_use_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise MalformedAIResponseError("No tool_use block in response")
        data = cast(ReviewToolOutput, tool_use_block.input)
        _require_review_fields(data)
        return StructuredReview(
            detected_language=data["detected_language"],
            summary=data["summary"],
            severity=data["severity"],
            score=data["score"],
            bugs=data.get("bugs", []),
            security_issues=data.get("security_issues", []),
            suggestions=data.get("suggestions", []),
            positives=data.get("positives", []),
        )

    async def review_pr_diff(self, pr_label: str, diff: str) -> StructuredReview:
        """Review a GitHub PR's diff, labeled for context (e.g. "owner/repo#1")."""
        code_context = f"Pull request {pr_label}:\n\n```diff\n{diff}\n```"
        return await self.review_structured(code=code_context, language="diff")

    async def review_stream(
        self, code: str, language: str = "python"
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
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
