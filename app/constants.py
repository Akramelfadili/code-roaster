from typing import Literal, get_args

Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_VALUES: tuple[Severity, ...] = get_args(Severity)

ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 2048
