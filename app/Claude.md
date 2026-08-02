# Code Roaster — CLAUDE.md (Backend)

## Stack
Python 3.12, FastAPI, Anthropic SDK, Pydantic v2, conda environment

## Project Structure
```
app/
├── __init__.py
├── constants.py        # All magic strings/numbers used anywhere in app/ (e.g. Severity, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS) — single source of truth, not just for values shared across multiple files
├── exceptions.py       # AppError base + all domain exceptions — see "Error Handling"
├── models/
│   ├── review.py        # Review request/response models
│   └── pr.py             # PullRequestRef, PR review request models
├── services/
│   ├── reviewer.py        # CodeReviewer class — all AI logic lives here
│   ├── github.py          # GitHubService — OAuth token exchange, PR URL parsing, diff fetch
│   └── github_errors.py   # GitHub-specific error translation (raise_for_github_response, is_rate_limited)
└── routes/
    ├── __init__.py
    ├── review.py       # /review/stream, /review/structured
    ├── auth.py         # /auth/github, /auth/github/callback — GitHub OAuth
    ├── pr.py           # /review/pr — PR diff review
    └── health.py       # /health
main.py              # App setup, lifespan, logging config, and the single AppError handler
```

## Imports
- Always use absolute imports starting from the project root (e.g. `from app.models import X`)
- Never use relative imports with `..`

## Python Standards
- No magic strings or numbers — define them as named constants in `app/constants.py`
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

## External API Calls
- Any class that talks to an external API or SDK — the GitHub REST API, the Anthropic SDK, anything added later — lives under `app/services/`. No exceptions for how central it is to the product (`CodeReviewer` included): one flat rule beats a "core vs. adapter" distinction that only makes sense in hindsight
- `httpx.AsyncClient` for all outbound HTTP calls (GitHub API, OAuth endpoints, etc.) — never the sync client, never `requests`
- Wrap calls in a service class under `app/services/` — routes never call `httpx` directly
- Accept an optional `transport: httpx.AsyncBaseTransport | None` on service constructors so tests can inject `httpx.MockTransport` instead of hitting the network
- Translate HTTP status codes into domain exceptions inside the service — never let a raw `httpx` exception or status code reach a route. See `app/services/github_errors.py`'s `raise_for_github_response` for the pattern: one function that maps a response's status code to the right `AppError` subclass, called by every method that makes an API call, instead of each method hand-rolling its own status-code branching

## Anthropic SDK Standards
- Always use `ANTHROPIC_MODEL` from `app/constants.py` (currently `claude-sonnet-4-6`) unless there's a specific reason not to
- Always include `cache_control: ephemeral` on system prompts
- Use `AsyncAnthropic` — never the sync client
- Streaming for text responses, `create()` for structured output
- Handle `RateLimitError` and `APIError` explicitly
- Log token usage on every call

## Error Handling

- Never let raw exceptions bubble up to the client
- Routes and services never catch exceptions and never log — they just raise. Logging and HTTP translation both happen in exactly one place: `main.py`'s `app_error_handler`
- All domain exceptions subclass `AppError` (`app/exceptions.py`). FastAPI resolves exception handlers by walking the exception's MRO, so the single handler registered on `AppError` in `main.py` also catches every subclass (`GitHubError`, `PRNotFoundError`, `AIProviderError`, ...) automatically — **adding a new failure mode never requires a new handler function in `main.py`**, just a new exception class

**To add a new domain exception:**
1. Subclass `AppError` directly, or an existing domain subclass (`GitHubError`, `ReviewError`) if it belongs there
2. Set `status_code` — required
3. Optionally override `log_level`: `logging.WARNING` for expected, user-fixable states (bad input, expired token, not found — no traceback attached); leave the `logging.ERROR` default for anything that signals a bug or an outage (attaches a full traceback)
4. Optionally override `user_message`: leave `None` to show the exception's own message to the client (safe for expected/actionable errors); set a fixed string to hide the real message instead (for unexpected/infra failures where the internal detail isn't useful, or safe, to expose)
5. Raise it with `raise SomeError("message")` — no logging call needed. Pass `debug_context="..."` for extra diagnostic detail (e.g. a raw API response body) that should be logged but never sent to the client

**Current exceptions**, as a reference:

| Exception | Status | Log level | Client sees |
|---|---|---|---|
| `AIProviderError` | 502 | ERROR | fixed message |
| `MalformedAIResponseError` | 500 | ERROR | fixed message |
| `GitHubError` (fallback, e.g. network failure) | 502 | ERROR | fixed message |
| `InvalidPRUrlError` | 400 | WARNING | own message |
| `GitHubAuthError` | 401 | WARNING | own message |
| `PRNotFoundError` | 404 | WARNING | own message |
| `GitHubRateLimitError` | 429 | WARNING | own message |

- `main.py` calls `logging.basicConfig(...)` once at import time — without it, `logging.getLogger(__name__)` calls anywhere in the app print bare, unformatted messages (no level, no timestamp, no logger name) via Python's fallback handler. Don't remove it, and don't add a second `basicConfig` call elsewhere
- Services translate *what went wrong* into the right exception type; `main.py` alone handles *logging and responding*. If you're tempted to add a `logger.error(...)` call inside a service or route, that's a sign the failure needs a new/adjusted `AppError` subclass instead

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
├── conftest.py             # shared fixtures (mock_reviewer, mock_github_service, client)
├── mocks.py                # shared mock data
├── test_routes.py          # /review/stream, /review/structured, /health
├── test_auth.py            # /auth/github, /auth/github/callback
├── test_pr.py              # /review/pr
└── test_github_service.py  # GitHubService unit tests (URL parsing, diff fetch, OAuth exchange)
```

**Async tests:** `pytest.ini` sets `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed. All async test functions are picked up automatically.

**Mocking the Anthropic client:**
- Never instantiate a real `CodeReviewer` in tests — it requires `ANTHROPIC_API_KEY` and hits the API
- `ASGITransport` does NOT trigger the FastAPI lifespan, so set `app.state.reviewer` directly in the fixture
- Use `MagicMock(spec=CodeReviewer)` as the base; set `review_structured` as `AsyncMock`; set `review_stream` as `MagicMock(side_effect=async_gen_fn)` since it returns an async generator (not a coroutine)

**Mocking GitHub calls:**
- Never hit the real GitHub API in tests
- At the route level: use `MagicMock(spec=GitHubService)` (the `mock_github_service` fixture), same pattern as `mock_reviewer` — set `app.state.github_service` in the `client` fixture
- At the service level: inject `httpx.MockTransport(handler)` via `GitHubService(..., transport=...)` and assert on the returned data or raised domain exception

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
