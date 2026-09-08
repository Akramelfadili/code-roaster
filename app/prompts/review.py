from typing import TypedDict

import anthropic

from app.constants import SEVERITY_VALUES, Severity

SECURITY_REVIEW_SYSTEM_PROMPT = """\
You are a security expert. Review the code for security vulnerabilities only.
Focus exclusively on: injection attacks, authentication issues, data exposure,
insecure dependencies.
Ignore style, performance, and readability. Only report security issues.\
"""

STRUCTURED_REVIEW_SYSTEM_PROMPT = (
    "You are an expert code reviewer. Perform a thorough review covering "
    "correctness, security, performance, and code quality. Use the provided "
    "tool to submit your structured findings. Always populate detected_language "
    "with the programming language you identify in the submitted code."
)


class ReviewToolOutput(TypedDict):
    """Shape of the arguments Claude submits via the `submit_code_review` tool.

    Kept next to `STRUCTURED_REVIEW_TOOL` since it's a typed mirror of that
    schema's `properties` — update both together.
    """

    detected_language: str
    summary: str
    severity: Severity
    score: int
    bugs: list[str]
    security_issues: list[str]
    suggestions: list[str]
    positives: list[str]


STRUCTURED_REVIEW_TOOL: anthropic.types.ToolParam = {
    "name": "submit_code_review",
    "description": (
        "Submit a structured code review with scored assessment "
        "across multiple dimensions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "detected_language": {
                "type": "string",
                "description": (
                    "The programming language of the submitted code "
                    "(e.g. 'Python', 'TypeScript'). Always populate this field."
                ),
            },
            "summary": {
                "type": "string",
                "description": (
                    "A concise overall summary of the code quality and main findings."
                ),
            },
            "severity": {
                "type": "string",
                "enum": list(SEVERITY_VALUES),
                "description": "Overall severity of issues found.",
            },
            "score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": (
                    "Overall code quality score from 1 (worst) to 10 (best)."
                ),
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
        "required": [
            "detected_language",
            "summary",
            "severity",
            "score",
            "bugs",
            "security_issues",
            "suggestions",
            "positives",
        ],
    },
}
