"""PreToolUse (Bash): enforce the git rules and keep .env out of the transcript."""

import json
import re
import subprocess
import sys

BLOCKING_EXIT_CODE = 2
PROTECTED_BRANCH = "main"
READS_DOTENV = (
    r"(^|[\s;&|])(cat|less|more|head|tail|grep|sed|awk|source|\.)\s+"
    r"[^|;&]*\.env\b(?!\.example)"
)
FORBIDDEN_PATTERNS = {
    r"\bgit\s+push\b": "Never push — the user pushes manually (CLAUDE.md → Git Rules).",
    r"--no-verify\b": "--no-verify is only for a hook broken by the environment. "
    "Fix the lint/type error, or ask the user.",
    READS_DOTENV: "Don't read .env — it holds live API keys. Read .env.example "
    "or app/config.py instead.",
}


def current_branch() -> str:
    """Return the checked-out branch name."""
    result = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    )
    return result.stdout.strip()


def main() -> None:
    command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    for pattern, reason in FORBIDDEN_PATTERNS.items():
        if re.search(pattern, command):
            print(f"Blocked: {reason}", file=sys.stderr)
            sys.exit(BLOCKING_EXIT_CODE)
    if re.search(r"\bgit\s+commit\b", command) and current_branch() == PROTECTED_BRANCH:
        print(
            "Blocked: never commit to main. Create a feature/, fix/ or refactor/ "
            "branch first.",
            file=sys.stderr,
        )
        sys.exit(BLOCKING_EXIT_CODE)


if __name__ == "__main__":
    main()
