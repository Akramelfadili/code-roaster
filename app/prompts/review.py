from typing import NotRequired, TypedDict

import anthropic

from app.constants import SEVERITY_VALUES, Severity
from app.models.review import Confidence

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
    "with the programming language you identify in the submitted code. Report "
    "each finding as its own item with a short title and an explanation, and "
    "set file and line numbers whenever the code under review lets you locate it."
)


class FindingToolOutput(TypedDict):
    """Shape of one finding Claude submits inside a `submit_code_review` list.

    A typed mirror of `_FINDING_SCHEMA` — update both together. `id` and
    `category` aren't asked of the model: the server generates the ID and
    derives the category from the list the finding was submitted in.
    """

    title: str
    explanation: str
    confidence: Confidence
    severity: NotRequired[Severity]
    file: NotRequired[str]
    line_start: NotRequired[int]
    line_end: NotRequired[int]
    suggestion: NotRequired[str]


class ReviewToolOutput(TypedDict):
    """Shape of the arguments Claude submits via the `submit_code_review` tool.

    Kept next to `STRUCTURED_REVIEW_TOOL` since it's a typed mirror of that
    schema's `properties` — update both together.
    """

    detected_language: str
    summary: str
    severity: Severity
    score: int
    bugs: list[FindingToolOutput]
    security_issues: list[FindingToolOutput]
    suggestions: list[FindingToolOutput]
    positives: list[FindingToolOutput]


_FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A one-line headline for the finding.",
        },
        "explanation": {
            "type": "string",
            "description": "Why this matters, in one to three sentences.",
        },
        "severity": {
            "type": "string",
            "enum": list(SEVERITY_VALUES),
            "description": "How serious the issue is. Omit for positives.",
        },
        "file": {
            "type": "string",
            "description": (
                "Path of the file the finding is in, exactly as it appears in the "
                "diff. Omit for pasted snippets or findings not tied to one file."
            ),
        },
        "line_start": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "First line the finding refers to: in the new version of the file "
                "for a diff, or in the snippet as submitted. Omit if not tied to "
                "specific lines."
            ),
        },
        "line_end": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "Last line the finding refers to; equal to line_start for a "
                "single line."
            ),
        },
        "suggestion": {
            "type": "string",
            "description": "A concrete fix or improvement, when there is one.",
        },
        "confidence": {
            "type": "string",
            "enum": [confidence.value for confidence in Confidence],
            "description": "How sure you are that this finding is correct.",
        },
    },
    "required": ["title", "explanation", "confidence"],
}


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
                "items": _FINDING_SCHEMA,
                "description": "Bugs or logical errors found in the code.",
            },
            "security_issues": {
                "type": "array",
                "items": _FINDING_SCHEMA,
                "description": "Security vulnerabilities or concerns.",
            },
            "suggestions": {
                "type": "array",
                "items": _FINDING_SCHEMA,
                "description": "Improvement suggestions.",
            },
            "positives": {
                "type": "array",
                "items": _FINDING_SCHEMA,
                "description": "Things done well in the code.",
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
