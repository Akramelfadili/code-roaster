# Code Roaster — CLAUDE.md (Backend)

## Stack
Python 3.12, FastAPI, Anthropic SDK, Pydantic v2, Voyage AI (embeddings), Chroma (vector store), Postgres via SQLAlchemy 2 async (`asyncpg`) + Alembic, conda environment `code-roaster`

## Project Structure
```
app/
├── __init__.py
├── main.py              # App setup, lifespan, logging config, and the exception handlers
├── config.py            # Settings — all env-loaded config, see "Configuration"
├── database.py          # Async engine, SessionFactory, Base, get_db/DbSession, init_db — see "Database"
├── constants.py         # Named constants shared across app/ (Severity, ANTHROPIC_MODEL, ...)
├── exceptions.py        # AppError base + all domain exceptions — see claude-docs/error-handling.md
├── pytest.ini           # asyncio_mode = auto, testpaths = tests
├── requirements.txt     # Runtime dependencies
├── requirements-dev.txt # pytest, ruff, mypy, bandit, pre-commit
├── README.md
├── models/
│   ├── __init__.py
│   ├── review.py        # Review request/response models, Finding + FindingCategory/Confidence
│   ├── pr.py            # PullRequestRef, PR review request models
│   ├── index.py         # IndexRepoRequest, IndexingJobStatus, IndexingSummary
│   └── db/              # SQLAlchemy ORM tables — importing the package registers them on Base.metadata
│       └── indexing.py  # IndexingJob (`indexing_jobs` table)
├── migrations/          # Alembic env.py, script template, versions/ — config in root alembic.ini
├── prompts/
│   ├── __init__.py
│   └── review.py        # System prompts, STRUCTURED_REVIEW_TOOL schema, ReviewToolOutput/FindingToolOutput
├── services/
│   ├── __init__.py
│   ├── reviewer.py      # CodeReviewer — all LLM calls; PR review consumes context from CodeRetriever
│   ├── github.py        # GitHubService — OAuth token exchange, PR URL parsing, diff fetch, repo file fetch
│   ├── github_errors.py # raise_for_github_response, is_rate_limited
│   ├── chunker.py       # CodeChunker + Chunk — splits source files for the RAG pipeline
│   ├── embedder.py      # Embedder — Chunks → vectors via Voyage AI
│   ├── vector_store.py  # VectorStore — persists and searches embeddings via Chroma
│   ├── indexer.py       # RepoIndexer + IndexingResult — fetch → chunk → embed → store
│   ├── retriever.py     # CodeRetriever — query → embed → search; the only place retrieval happens
│   └── indexing_jobs.py # create/get indexing jobs + run_indexing_job — job state read/written in Postgres
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

## Database
**Rule: all job state lives in Postgres, never in memory.** No job status, progress or result on `app.state`, in module globals or in caches — `app.state` holds services and the `session_factory` only. Rationale: `ARCHITECTURE.md` §3.8.

- `app/database.py` is the only place an engine or session factory is created. Routes get a session with the `DbSession` dependency (`Annotated[AsyncSession, Depends(get_db)]`); `get_db` reads `app.state.session_factory`
- Background tasks never reuse the request's session (it is closed by then) — they receive `app.state.session_factory` as an argument and open a short session per write
- ORM tables live in `app/models/db/` and inherit `Base`; a new table module must be imported in `app/models/db/__init__.py` so Alembic (and the test fixture's `create_all`) see it. API responses stay Pydantic — the service maps rows to response models, routes never return ORM objects
- DB access lives in services (`app/services/`), never in routes. Translate DB errors the caller can act on into domain exceptions in the service (pattern: `IntegrityError` → `IndexingAlreadyInProgressError` in `create_indexing_job`)
- Enforce invariants in the schema (unique/partial indexes, `NOT NULL`), not with check-then-write code — a check in Python races across workers
- Store `StrEnum`s as their lowercase values (`Enum(..., values_callable=...)`), timestamps as `DateTime(timezone=True)`
- **Schema setup** (`init_db`, called by the lifespan): always `alembic upgrade head`, in every environment. Never add a `create_all` shortcut to app code — it never alters existing tables and drifts from the migrations
- **Orphaned jobs** (`fail_orphaned_indexing_jobs`, called by the lifespan after `init_db`): `pending`/`running` jobs not updated for `INDEXING_JOB_TIMEOUT_SECONDS` become `failed` with `INDEXING_JOB_ORPHANED_ERROR`. A future job type with in-process execution (V5 agent runs) needs the same sweep, and its runner must update `updated_at` more often than the timeout
- **Every model change ships with a migration**, run from the project root:
  - `alembic revision --autogenerate -m "describe change"` → review the file in `app/migrations/versions/` (autogenerate misses some things, e.g. enum value changes)
  - `alembic upgrade head` / `alembic downgrade -1`; `alembic check` fails if models and migrations have drifted
  - Migrations are frozen snapshots: write literals in them, never import `app.constants`
- A model change isn't live, even in development, until its migration exists — the app only ever runs migrations

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

## Review Findings
Every item in `bugs`, `security_issues`, `suggestions` and `positives` is a `Finding` (`app/models/review.py`) — never a plain string. Contract and rationale: `ARCHITECTURE.md` §3.7.

| Field | Type | Set by |
|---|---|---|
| `id` | `str` (UUID4, `default_factory`) | Server |
| `category` | `FindingCategory`: `bug` / `security` / `suggestion` / `positive` | Server — from the tool list the finding came in |
| `severity` | `Severity \| None` — omitted for positives | Claude |
| `file`, `line_start`, `line_end` | `str \| None`, `int \| None` (≥ 1) | Claude |
| `title`, `explanation` | `str` (required) | Claude |
| `suggestion` | `str \| None` | Claude |
| `confidence` | `Confidence`: `low` / `medium` / `high` (required) | Claude |

- **`id` and `category` are always set server-side, never by Claude.** Keep them out of `_FINDING_SCHEMA` and `FindingToolOutput`; `CodeReviewer` stamps the category from the list and `Finding` generates the ID. Never read either from tool input
- `_FINDING_SCHEMA` (tool JSON schema) and `FindingToolOutput` (its TypedDict mirror) in `app/prompts/review.py` change together — and together with `Finding` and the frontend `FindingSchema`
- Build findings only through `Finding.model_validate` in `CodeReviewer`. A non-object item or a `ValidationError` becomes `MalformedAIResponseError` — never let a raw `TypeError`/`ValidationError` escape
- Adding a field: optional (`| None = None`) unless the review is useless without it — a required field Claude omits fails the whole review

## Code Quality
- Pre-commit runs ruff (lint + format), mypy (strict) and bandit on staged `.py` files — configs live at the project root (`ruff.toml`, `mypy.ini`, `.bandit`, `.pre-commit-config.yaml`)
- Run checks via `make lint-back`, `make format-back`, `make type-back`, `make security-back` (see root CLAUDE.md)
- `git commit --no-verify` only when a hook is broken by an environment issue — never to bypass a real lint/type error

@claude-docs/error-handling.md
@claude-docs/rag-pipeline.md
@claude-docs/testing.md
