# Code Roaster — CLAUDE.md (Backend)

## Stack
Python 3.12, FastAPI, Anthropic SDK, Pydantic v2, Voyage AI (embeddings), Chroma (vector store), Postgres via SQLAlchemy 2 async (`asyncpg`) + Alembic, conda environment `code-roaster`

## Project Structure
```
app/
├── __init__.py
├── main.py              # App setup, lifespan, logging config, and the exception handlers
├── config.py            # Settings — all env-loaded config, see "Configuration"
├── database.py          # Async engine, SessionFactory, Base, enum_values, get_db/DbSession/FunctionScopedDbSession, init_db — see "Database"
├── constants.py         # Named constants shared across app/ (Severity, ANTHROPIC_MODEL, ...)
├── exceptions.py        # AppError base + all domain exceptions, incl. V5 agent errors — see claude-docs/error-handling.md
├── pytest.ini           # asyncio_mode = auto, testpaths = tests
├── requirements.txt     # Runtime dependencies
├── requirements-dev.txt # pytest, ruff, mypy, bandit, pre-commit
├── README.md
├── models/
│   ├── __init__.py
│   ├── review.py        # Review request/response models, Finding + FindingCategory/Confidence
│   ├── pr.py            # PullRequestRef, PR review request models
│   ├── index.py         # IndexRepoRequest, IndexingJobStatus, IndexingSummary
│   ├── review_job.py    # ReviewJobCreated, ReviewJobStatus, ReviewEventMessage (the SSE payload)
│   └── db/              # SQLAlchemy ORM tables — importing the package registers them on Base.metadata
│       ├── indexing.py  # IndexingJob (`indexing_jobs` table)
│       ├── review.py    # ReviewJob (`reviews`) + ReviewEvent (`review_events`, the job's event log)
│       └── spend.py     # DailySpend (`daily_spend`) — AI spend per UTC day, for the cost budget
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
│   ├── cost_budget.py   # CostBudget — checks and records daily AI spend in Postgres
│   ├── vector_store.py  # VectorStore — persists and searches embeddings via Chroma
│   ├── indexer.py       # RepoIndexer + IndexingResult — fetch → chunk → embed → store
│   ├── retriever.py     # CodeRetriever — query → embed → search; the only place retrieval happens
│   ├── indexing_jobs.py # create/get indexing jobs + run_indexing_job — job state read/written in Postgres
│   └── review_jobs.py   # create/get/run review jobs + stream_review_events — see "Review Jobs"
├── routes/
│   ├── __init__.py
│   ├── review.py        # /review/stream, /review/structured
│   ├── auth.py          # /auth/github, /auth/github/callback — GitHub OAuth
│   ├── pr.py            # /review/pr (sync), /review/pr/async + /review/pr/{job_id}/events (job + SSE)
│   ├── index.py         # /index/repo, /index/status/{repo_id} — background repo indexing
│   └── health.py        # /health
└── tests/               # conftest.py, mocks.py, one test_<module>.py per module — see claude-docs/testing.md
```

## Imports
- Always use absolute imports from the project root (`from app.models import X`) — never relative imports with `..`

## Python Standards
- Constants referenced by more than one module live in `app/constants.py`; module-private tuning values (chunk sizes, Voyage model name, batch size) stay module-local
- Docstrings on every class and public method
- `#` comments only explain *why* (decisions, limitations, workarounds) — never restate the code, log a fix, divide sections or keep commented-out code. Full rule in root CLAUDE.md
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
- **Streaming (SSE) routes use `FunctionScopedDbSession`, never `DbSession`.** `DbSession` stays open until the response ends, so a minutes-long stream would hold a pooled connection the whole time. `FunctionScopedDbSession` closes before the body streams. The stream itself opens a short session per poll from `app.state.session_factory`. Any dependency that takes it must also be declared `Depends(..., scope="function")`
- Background tasks never reuse the request's session (it is closed by then) — they receive `app.state.session_factory` as an argument and open a short session per write
- ORM tables live in `app/models/db/` and inherit `Base`; a new table module must be imported in `app/models/db/__init__.py` so Alembic (and the test fixture's `create_all`) see it. API responses stay Pydantic — the service maps rows to response models, routes never return ORM objects
- DB access lives in services (`app/services/`), never in routes. Translate DB errors the caller can act on into domain exceptions in the service (pattern: `IntegrityError` → `IndexingAlreadyInProgressError` in `create_indexing_job`)
- Enforce invariants in the schema (unique/partial indexes, `NOT NULL`), not with check-then-write code — a check in Python races across workers
- Store `StrEnum`s as their lowercase values (`Enum(..., values_callable=enum_values)`), timestamps as `DateTime(timezone=True)`. An enum that will keep growing (`ReviewEventType`) uses `native_enum=False`, a `VARCHAR`, so a new value needs no migration. Closed sets (job states) stay native Postgres enums
- **Schema setup** (`init_db`, called by the lifespan): always `alembic upgrade head`, in every environment. Never add a `create_all` shortcut to app code — it never alters existing tables and drifts from the migrations
- **Orphaned jobs** (`fail_orphaned_indexing_jobs` and `fail_orphaned_review_jobs`, called by the lifespan after `init_db`): `pending`/`running` jobs not updated for `INDEXING_JOB_TIMEOUT_SECONDS` / `REVIEW_JOB_TIMEOUT_SECONDS` become `failed` with the matching `*_ORPHANED_ERROR`; swept review jobs also get their terminal `failed` event. Every job type with in-process execution needs the same sweep, wired in the lifespan, and its runner must update `updated_at` more often than the timeout
- **Every model change ships with a migration**, run from the project root:
  - `alembic revision --autogenerate -m "describe change"` → review the file in `app/migrations/versions/` (autogenerate misses some things, e.g. enum value changes)
  - `alembic upgrade head` / `alembic downgrade -1`; `alembic check` fails if models and migrations have drifted
  - Migrations are frozen snapshots: write literals in them, never import `app.constants`
- A model change isn't live, even in development, until its migration exists — the app only ever runs migrations

## Review Jobs
`POST /review/pr/async` → `reviews` row + `202 {job_id}` + `run_review_job` in `BackgroundTasks`; `GET /review/pr/{job_id}/events` streams the job over SSE. The synchronous `POST /review/pr` stays as is. Design and event table: `ARCHITECTURE.md` §3.9.

| Event `type` (`ReviewEventType`) | `data` |
|---|---|
| `retrieving`, `reviewing` | `null` — emitted from `CodeReviewer`'s `on_stage` callback |
| `finding` | one `Finding`, as `model_dump(mode="json")` |
| `completed` (terminal) | the full `StructuredReviewResponse` (also stored in `reviews.result`) |
| `failed` (terminal) | `{"error": <client_message or INTERNAL_SERVER_ERROR_MESSAGE>}` |

- **Every step is an event in `review_events`. Never push events through memory** (no queues, no `asyncio.Event`s on `app.state`). The SSE stream only polls the table, which is what makes it work across workers and lets clients resume with `Last-Event-ID`
- **Write a state change and its event in one transaction** through `_record_events`. It also bumps `updated_at`, which keeps a live job from being swept
- **Every job ends with exactly one terminal event** (`completed` or `failed`); `stream_review_events` stops on it. A new failure path must go through `_mark_failed`, and a new sweep must append the `failed` event
- **Adding an event type** (e.g. a V5 agent step): add it to `ReviewEventType` (no migration — `type` is a `VARCHAR`), document its `data` shape here and in `ARCHITECTURE.md` §3.9, and add it to the frontend schema when a client consumes it. Never reuse an existing type for a different payload
- **The runner fetches the diff before it retrieves any context.** `repo_id` comes from the parsed PR URL, never from the client, and is only used once `fetch_pr_diff` has succeeded with the caller's token. The GitHub token is a background task argument, never stored on the row
- **SSE route shape:** `response_class=EventSourceResponse`, an async generator that yields `ServerSentEvent(data=<ReviewEventMessage>, id=str(event.id))`. Check the job exists in a function-scoped dependency, so a miss is a JSON 404 before the stream starts

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
- Check `stop_reason` after every call through `_raise_if_truncated`: `max_tokens` raises `OutputTruncatedError`, never a partial result
- Log token usage and approximate cost on every call through `_log_usage` in `reviewer.py`; never send more context than needed
- Pricing constants (`ANTHROPIC_*_COST_PER_MTOK_USD`) are for `ANTHROPIC_MODEL`, so change them whenever the model changes

## Input Caps & Cost Budget
**Rule: no LLM or embedding call takes unbounded input.** Agents multiply calls per run, so an uncapped input can drain the API balance. Rationale: `ARCHITECTURE.md` §3.10. All caps live in `app/constants.py`.

| Input | Cap | Enforced in | On overflow |
|---|---|---|---|
| `ReviewRequest.code` | `MAX_CODE_CHARS` = 50,000 | `Field(max_length=...)` | `422` |
| `ReviewRequest.language` | `MAX_LANGUAGE_CHARS` = 500 | `Field(max_length=...)` | `422` |
| `PRReviewRequest.pr_url` | `MAX_PR_URL_CHARS` = 500 | `Field(max_length=...)` | `422` |
| PR diff | `MAX_DIFF_CHARS` = 100,000 | `GitHubService.fetch_pr_diff` | Truncated, WARNING logged |
| Retrieved context | `MAX_CONTEXT_CHARS` = 20,000 | `_fit_context_budget` in `reviewer.py` | Lowest-ranked chunks dropped, WARNING logged |
| Embedding query | `MAX_QUERY_CHARS` = 10,000 | `Embedder.embed_query` | Truncated, WARNING logged |

- **Client input is rejected and server-built input is truncated.** A user can fix an oversized request field, so it gets a `422`. A diff, context or query the server fetches or builds is cut down so the review still runs. Truncation logs at WARNING (a documented exception to "services never log", like retrieval)
- **A new LLM or embedding call path needs a cap before it ships.** Add the constant to `app/constants.py`, enforce it at the boundary (Pydantic field for client input, the service for fetched or built input), and add a row here
- **Every Claude and Voyage AI call is charged to the daily budget.** Call `CostBudget.ensure_available()` before the call and `CostBudget.record(cost_usd)` after it (before `_raise_if_truncated`). It raises `BudgetExceededError` (`429`) once today's spend reaches `settings.daily_cost_budget_usd` (env `DAILY_COST_BUDGET_USD`, default `10.0`). The running total is the `daily_spend` table, never memory. `CodeReviewer` and `Embedder` take the budget as a constructor argument; only tests leave it out. A new call path must go through it too

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
