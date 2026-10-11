# Code Roaster — CLAUDE.md (Backend)

## Stack
Python 3.12, FastAPI, Anthropic SDK, Pydantic v2, Voyage AI (embeddings), Chroma (vector store), conda environment `code-roaster`

## Project Structure
```
app/
├── __init__.py
├── main.py              # App setup, lifespan, logging config, and the exception handlers
├── config.py            # Settings — all env-loaded config, see "Configuration"
├── constants.py         # Named constants shared across app/ (Severity, ANTHROPIC_MODEL, ...)
├── exceptions.py        # AppError base + all domain exceptions — see claude-docs/error-handling.md
├── pytest.ini           # asyncio_mode = auto, testpaths = tests
├── requirements.txt     # Runtime dependencies
├── requirements-dev.txt # pytest, ruff, mypy, bandit, pre-commit
├── README.md
├── models/
│   ├── __init__.py
│   ├── review.py        # Review request/response models
│   ├── pr.py            # PullRequestRef, PR review request models
│   └── index.py         # IndexRepoRequest, IndexingJobStatus, IndexingSummary
├── prompts/
│   ├── __init__.py
│   └── review.py        # System prompts + STRUCTURED_REVIEW_TOOL schema for CodeReviewer
├── services/
│   ├── __init__.py
│   ├── reviewer.py      # CodeReviewer — all AI logic, incl. RAG-augmented PR review
│   ├── github.py        # GitHubService — OAuth token exchange, PR URL parsing, diff fetch, repo file fetch
│   ├── github_errors.py # raise_for_github_response, is_rate_limited
│   ├── chunker.py       # CodeChunker + Chunk — splits source files for the RAG pipeline
│   ├── embedder.py      # Embedder — Chunks → vectors via Voyage AI
│   ├── vector_store.py  # VectorStore — persists and searches embeddings via Chroma
│   ├── indexer.py       # RepoIndexer + IndexingResult — fetch → chunk → embed → store
│   └── indexing_jobs.py # run_indexing_job — background wrapper recording job progress/outcome
├── routes/
│   ├── __init__.py
│   ├── review.py        # /review/stream, /review/structured
│   ├── auth.py          # /auth/github, /auth/github/callback — GitHub OAuth
│   ├── pr.py            # /review/pr — PR diff review
│   ├── index.py         # /index/repo, /index/status/{repo_id} — background repo indexing
│   └── health.py        # /health
└── tests/               # conftest.py, mocks.py, one test_<module>.py per module — see claude-docs/testing.md
```

## Imports
- Always use absolute imports from the project root (`from app.models import X`) — never relative imports with `..`

## Python Standards
- Constants referenced by more than one module live in `app/constants.py`; module-private tuning values (chunk sizes, Voyage model name, batch size) stay module-local
- Docstrings on every class and public method
- f-strings for string formatting
- `pathlib` over `os.path`
- Type hints, explicit return types, and no `Any` are enforced by mypy strict

## FastAPI Standards
- Pydantic models for all request/response bodies — never raw dicts
- Input validation lives in Pydantic models (`field_validator`), not routes
- Lifespan for startup/shutdown (not deprecated `@app.on_event`); shared services live on `app.state`
- Router prefix and tags on all routers; one router per domain (review, auth, pr, index, health)

## Configuration
- All configuration comes from `Settings` (`app/config.py`), loaded once from env vars / `.env` — never call `os.environ`/`os.getenv` anywhere else in `app/`
- New config values (API keys, client secrets, feature toggles) are added as typed fields on `Settings`

## External API Calls
- Every class that talks to an external API or SDK lives under `app/services/` — no exceptions, `CodeReviewer` included
- `httpx.AsyncClient` for all outbound HTTP — never the sync client, never `requests`; routes never call `httpx` directly
- Service constructors accept an optional `transport: httpx.AsyncBaseTransport | None` (or an SDK `client`) so tests inject fakes
- Translate status codes into domain exceptions inside the service, in one function called by every method (pattern: `raise_for_github_response` in `app/services/github_errors.py`)

## Anthropic SDK Standards
- Use `ANTHROPIC_MODEL` from `app/constants.py` (currently `claude-sonnet-4-6`) unless there's a specific reason not to
- `AsyncAnthropic` only — never the sync client
- Streaming for text responses, `create()` with a tool schema for structured output
- `cache_control: ephemeral` on every system prompt
- Handle `RateLimitError` and `APIError` explicitly
- Log input/output token usage on every call; never send more context than needed

## Code Quality
- Pre-commit runs ruff (lint + format), mypy (strict) and bandit on staged `.py` files — configs live at the project root (`ruff.toml`, `mypy.ini`, `.bandit`, `.pre-commit-config.yaml`)
- Run checks via `make lint-back`, `make format-back`, `make type-back`, `make security-back` (see root CLAUDE.md)
- `git commit --no-verify` only when a hook is broken by an environment issue — never to bypass a real lint/type error

@claude-docs/error-handling.md
@claude-docs/rag-pipeline.md
@claude-docs/testing.md
