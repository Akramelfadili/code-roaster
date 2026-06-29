import os
from collections.abc import AsyncIterator
from typing import Literal, TypedDict, cast

import anthropic
from anthropic import APIError
from anthropic.types import TextBlock

from app.exceptions import AIProviderError, MalformedAIResponseError
from app.prompts.review import SECURITY_REVIEW_SYSTEM_PROMPT, STRUCTURED_REVIEW_TOOL


class _ReviewToolOutput(TypedDict):
    summary: str
    severity: Literal["low", "medium", "high", "critical"]
    score: int
    bugs: list[str]
    security_issues: list[str]
    suggestions: list[str]
    positives: list[str]


class StructuredReview:
    def __init__(
        self,
        summary: str,
        severity: Literal["low", "medium", "high", "critical"],
        score: int,
        bugs: list[str],
        security_issues: list[str],
        suggestions: list[str],
        positives: list[str],
    ) -> None:
        self.summary = summary
        self.severity = severity
        self.score = score
        self.bugs = bugs
        self.security_issues = security_issues
        self.suggestions = suggestions
        self.positives = positives


class CodeReviewer:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = "claude-sonnet-4-6"

    async def review(self, code: str, language: str = "python") -> str:
        try:
            response = await self.client.messages.create(
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
                        "content": (
                            f"Review this {language} code:"
                            f"\n\n```{language}\n{code}\n```"
                        ),
                    }
                ],
            )
        except APIError as e:
            raise AIProviderError("Anthropic API call failed") from e
        block = response.content[0]
        if not isinstance(block, TextBlock):
            raise MalformedAIResponseError(
                f"Expected TextBlock, got {type(block).__name__}"
            )
        return block.text

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
                        "text": (
                            "You are an expert code reviewer. Perform a thorough "
                            "review covering correctness, security, performance, "
                            "and code quality. Use the provided tool to submit "
                            "your structured findings."
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[STRUCTURED_REVIEW_TOOL],
                tool_choice={"type": "tool", "name": "submit_code_review"},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Review this {language} code:"
                            f"\n\n```{language}\n{code}\n```"
                        ),
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
        data = cast(_ReviewToolOutput, tool_use_block.input)
        return StructuredReview(
            summary=data["summary"],
            severity=data["severity"],
            score=data["score"],
            bugs=data["bugs"],
            security_issues=data["security_issues"],
            suggestions=data["suggestions"],
            positives=data["positives"],
        )

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
                    "content": (
                        f"Review this {language} code:\n\n```{language}\n{code}\n```"
                    ),
                }
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
