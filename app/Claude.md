# Code Roaster — CLAUDE.md (Backend)

## Stack
Python 3.12, FastAPI, Anthropic SDK, Pydantic v2, conda environment

## Project Structure
```
app/
├── __init__.py
├── models.py        # All Pydantic models
├── reviewer.py      # CodeReviewer class — all AI logic lives here
└── routes/
    ├── __init__.py
    └── review.py    # All route handlers
main.py              # App setup and lifespan only
```

## Imports
- Always use absolute imports starting from the project root (e.g. `from app.models import X`)
- Never use relative imports with `..`

## Python Standards
- Type hints on every function — always
- Docstrings on every class and public method
- No `Any` type — ever
- Explicit return types on all functions
- f-strings for string formatting
- `pathlib` over `os.path`

## FastAPI Standards
- Pydantic models for all request/response bodies — never raw dicts
- HTTPException with clear status codes and messages
- Lifespan for startup/shutdown (not deprecated @app.on_event)
- Router prefix and tags on all routers
- One router per domain (review, auth, etc.)

## Anthropic SDK Standards
- Always use `claude-sonnet-4-6` unless there's a specific reason not to
- Always include `cache_control: ephemeral` on system prompts
- Use `AsyncAnthropic` — never the sync client
- Streaming for text responses, `create()` for structured output
- Handle `RateLimitError` and `APIError` explicitly
- Log token usage on every call

## Error Handling
- Never let raw exceptions bubble up to the client
- Always return structured error responses
- Log errors with context (what failed, what inputs caused it)

## Cost Optimization
- Cache system prompts with `cache_control: ephemeral`
- Use Haiku for simple/cheap tasks, Sonnet for everything else
- Never send more context than needed
- Log input/output token counts for every API call

## Naming Conventions
- Classes: PascalCase
- Functions/variables: snake_case
- Constants: UPPER_SNAKE_CASE
- Files: snake_case

## Testing

**Stack:** `pytest`, `pytest-asyncio`, `httpx` — install from `requirements-dev.txt`

**Run the suite:**
```
conda run -n code-roaster python -m pytest tests/ -v
```

**Folder structure:**
```
tests/
├── conftest.py       # shared fixtures (mock_reviewer, client)
└── test_routes.py    # one file per router
```

**Async tests:** `pytest.ini` sets `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed. All async test functions are picked up automatically.

**Mocking the Anthropic client:**
- Never instantiate a real `CodeReviewer` in tests — it requires `ANTHROPIC_API_KEY` and hits the API
- `ASGITransport` does NOT trigger the FastAPI lifespan, so set `app.state.reviewer` directly in the fixture
- Use `MagicMock(spec=CodeReviewer)` as the base; set `review` and `review_structured` as `AsyncMock`; set `review_stream` as `MagicMock(side_effect=async_gen_fn)` since it returns an async generator (not a coroutine)

**Naming:** `test_<what>_<expected_outcome>` — e.g. `test_empty_code_returns_422`, `test_happy_path_returns_all_fields`

**Group tests by endpoint** using classes: `class TestReview`, `class TestReviewStream`, `class TestReviewStructured`

## Code Quality

Four tools enforce quality automatically on every commit via pre-commit. Activate the conda env before committing — the `mypy` and `bandit` hooks run in isolated environments, but the other two (`ruff`) are self-contained.

### Tools

**Ruff** — linter and formatter (replaces flake8, isort, black)
- Config: `ruff.toml` at project root
- Rules: `E/F` (pycodestyle/pyflakes), `I` (isort), `N` (naming), `UP` (pyupgrade), `S` (security), `B` (bugbear), `C4` (comprehensions), `PTH` (pathlib)
- `S101` (assert-in-test) is suppressed in `**/tests/**`

**Mypy** — static type checker in strict mode
- Config: `mypy.ini` at project root (`strict = true`, `python_version = 3.12`)
- Strict means: no untyped defs, no implicit `Any`, explicit return types on everything

**Bandit** — security-focused AST scanner
- Config: `.bandit` at project root
- Skips `app/tests/` (via pre-commit `exclude` pattern)

**Pre-commit** — runs all of the above on staged files before every commit
- Config: `.pre-commit-config.yaml` at project root
- Hook order: trailing-whitespace → end-of-file-fixer → ruff lint → ruff format → mypy → bandit

### Run manually

```bash
# Lint and auto-fix
conda run -n code-roaster python -m ruff check app/ --fix

# Format
conda run -n code-roaster python -m ruff format app/

# Type check
conda run -n code-roaster python -m mypy app/

# Security scan (excluding tests)
conda run -n code-roaster python -m bandit -c .bandit -r app/ -x app/tests

# Run all hooks against every file
conda run -n code-roaster pre-commit run --all-files
```

### Skip hooks (emergency only)

```bash
git commit --no-verify -m "chore: ..."
```

Only use `--no-verify` if a hook is broken by an environment issue, never to bypass a real lint/type error.
