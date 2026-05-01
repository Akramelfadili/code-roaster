import os
from collections.abc import AsyncIterator
from typing import Literal

import anthropic

SYSTEM_PROMPT = """\You are a security expert. Review the code for security vulnerabilities only.
Focus exclusively on: injection attacks, authentication issues, data exposure, insecure dependencies.
Ignore style, performance, and readability. Only report security issues.\
"""

STRUCTURED_REVIEW_TOOL: anthropic.types.ToolParam = {
    "name": "submit_code_review",
    "description": "Submit a structured code review with scored assessment across multiple dimensions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A concise overall summary of the code quality and main findings.",
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Overall severity of issues found.",
            },
            "score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Overall code quality score from 1 (worst) to 10 (best).",
            },
            "bugs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of bugs or logical errors found in the code.",
            },
            "security_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of security vulnerabilities or concerns.",
            },
            "suggestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of improvement suggestions.",
            },
            "positives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of things done well in the code.",
            },
        },
        "required": ["summary", "severity", "score", "bugs", "security_issues", "suggestions", "positives"],
    },
}


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
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Review this {language} code:\n\n"
                        f"```{language}\n{code}\n```"
                    ),
                }
            ],
        )
        return response.content[0].text

    async def review_structured(self, code: str, language: str = "python") -> StructuredReview:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are an expert code reviewer. Perform a thorough review covering "
                        "correctness, security, performance, and code quality. Use the provided "
                        "tool to submit your structured findings."
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
                        f"Review this {language} code:\n\n"
                        f"```{language}\n{code}\n```"
                    ),
                }
            ],
        )

        tool_use_block = next(b for b in response.content if b.type == "tool_use")
        data = tool_use_block.input
        return StructuredReview(
            summary=data["summary"],
            severity=data["severity"],
            score=data["score"],
            bugs=data["bugs"],
            security_issues=data["security_issues"],
            suggestions=data["suggestions"],
            positives=data["positives"],
        )

    async def review_stream(self, code: str, language: str = "python") -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Review this {language} code:\n\n"
                        f"```{language}\n{code}\n```"
                    ),
                }
            ],
        ) as stream:
            async for text in stream.text_stream:
                yield text
