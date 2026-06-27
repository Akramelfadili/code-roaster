import anthropic

SECURITY_REVIEW_SYSTEM_PROMPT = """\
You are a security expert. Review the code for security vulnerabilities only.
Focus exclusively on: injection attacks, authentication issues, data exposure,
insecure dependencies.
Ignore style, performance, and readability. Only report security issues.\
"""

STRUCTURED_REVIEW_TOOL: anthropic.types.ToolParam = {
    "name": "submit_code_review",
    "description": (
        "Submit a structured code review with scored assessment "
        "across multiple dimensions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "A concise overall summary of the code quality and main findings."
                ),
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
