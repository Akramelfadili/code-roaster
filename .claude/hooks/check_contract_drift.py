"""Stop: block finishing while a cross-file contract is half-updated."""

import json
import subprocess
import sys

ORM_DIR = "app/models/db/"
MIGRATIONS_DIR = "app/migrations/versions/"
FINDING_BACKEND_FILES = ["app/models/review.py", "app/prompts/review.py"]
FINDING_MARKERS = ("Finding", "_FINDING_SCHEMA")
FINDING_FRONTEND_FILE = "frontend/src/types/review.ts"
ARCHITECTURE_FILE = "ARCHITECTURE.md"
NEW_MODULE_DIRS = ("app/services/", "app/routes/")


def git(*args: str) -> str:
    """Return stdout of a git command."""
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def find_drift() -> list[str]:
    """Return one message per half-updated contract."""
    untracked = set(git("ls-files", "--others", "--exclude-standard").split())
    changed = set(git("diff", "--name-only", "HEAD").split()) | untracked
    problems = []
    if any(f.startswith(ORM_DIR) for f in changed) and not any(
        f.startswith(MIGRATIONS_DIR) for f in changed
    ):
        problems.append(
            f"ORM models in {ORM_DIR} changed but no migration exists. Run "
            '`alembic revision --autogenerate -m "..."` and review it '
            "(app/CLAUDE.md → Database)."
        )
    finding_diff = git("diff", "HEAD", "--", *FINDING_BACKEND_FILES)
    if (
        any(marker in finding_diff for marker in FINDING_MARKERS)
        and FINDING_FRONTEND_FILE not in changed
    ):
        problems.append(
            "Finding / _FINDING_SCHEMA / FindingToolOutput changed but the frontend "
            f"FindingSchema ({FINDING_FRONTEND_FILE}) did not (ARCHITECTURE.md §3.7)."
        )
    new_modules = sorted(f for f in untracked if f.startswith(NEW_MODULE_DIRS))
    if new_modules and ARCHITECTURE_FILE not in changed:
        problems.append(
            f"New module(s) {', '.join(new_modules)} but {ARCHITECTURE_FILE} §4.1 and "
            "the app/CLAUDE.md structure tree were not updated."
        )
    return problems


def main() -> None:
    if json.load(sys.stdin).get("stop_hook_active"):
        return
    problems = find_drift()
    if problems:
        bullets = "\n- ".join(problems)
        reason = f"Before finishing, fix or explicitly justify:\n- {bullets}"
        print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
