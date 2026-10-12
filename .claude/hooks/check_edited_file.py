"""PostToolUse: lint, format and type-check the file Claude just edited."""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_EXTENSIONS = {".ts", ".tsx"}
BLOCKING_EXIT_CODE = 2


def run(command: list[str], cwd: Path) -> str:
    """Run a command; return its output if it failed, else an empty string."""
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return "" if result.returncode == 0 else result.stdout + result.stderr


def check_python(path: Path) -> list[str]:
    """Ruff fix + format the file, then mypy strict on app/ (cached, ~0.5s)."""
    run(["ruff", "format", str(path)], PROJECT_ROOT)
    return [
        run(["ruff", "check", "--fix", str(path)], PROJECT_ROOT),
        run(["mypy", "app/"], PROJECT_ROOT),
    ]


def check_frontend(path: Path) -> list[str]:
    """Prettier-write the file, ESLint it, then type-check the app (~6s total)."""
    run(["npx", "prettier", "--write", str(path)], FRONTEND_DIR)
    return [
        run(["npx", "eslint", "--max-warnings=0", str(path)], FRONTEND_DIR),
        run(["npx", "tsc", "-b", "tsconfig.app.json", "--noEmit"], FRONTEND_DIR),
    ]


def main() -> None:
    payload = json.load(sys.stdin)
    path = Path(payload.get("tool_input", {}).get("file_path", ""))
    if not path.is_file() or not path.resolve().is_relative_to(PROJECT_ROOT):
        return
    relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    if relative.startswith("app/") and path.suffix == ".py":
        failures = check_python(path)
    elif relative.startswith("frontend/src/") and path.suffix in FRONTEND_EXTENSIONS:
        failures = check_frontend(path)
    else:
        return
    report = "\n".join(failure for failure in failures if failure)
    if report:
        print(f"Checks failed after editing {relative}:\n{report}", file=sys.stderr)
        sys.exit(BLOCKING_EXIT_CODE)


if __name__ == "__main__":
    main()
