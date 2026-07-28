from typing import Literal, get_args

Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_VALUES: tuple[Severity, ...] = get_args(Severity)
