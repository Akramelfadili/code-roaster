# Code Roaster — Architecture

> A living document. It explains **why** the system is shaped the way it is, not only what exists.
> Conventions and step-by-step "how to" rules live in `CLAUDE.md`, `app/CLAUDE.md` and `frontend/CLAUDE.md`. This file links to them instead of repeating them.
> Last reviewed: 2026-10-11 (branch `refactor/extract-code-retriever`).

---

## 1. System Overview

Code Roaster is an AI code reviewer. There are two ways in:

- **Paste code:** submit a snippet and watch the review stream in, then get a structured result.
- **Review a pull request:** sign in with GitHub, paste a PR URL, and the backend fetches the diff and reviews it.

Either way, the output has the same structure: a **score (1–10)**, an overall **severity**, a **summary**, and four lists of **findings**: **bugs**, **security issues**, **suggestions** and **positives**.

Each finding is a structured object, not a sentence. It has a title, an explanation, a confidence level and, when it can be located, a file and line range. That lets findings link to code, become inline PR comments, and be evaluated one by one. The full contract is in §3.7.

**Who it's for:** developers who want a fast, opinionated second pair of eyes before a human review.

**Core value:** the feedback is structured and consistent, so it is quick to scan and act on and easy to compare across runs. Streaming keeps the wait from feeling slow. It is also a learning project for AI engineering, so each new version adds a technique: streaming, tool use, OAuth, then RAG, then agents.

```
┌──────────────────────┐   /api/*   ┌──────────────────────┐     ┌──────────────────┐
│ React SPA (Vite)     │ ─────────▶ │ FastAPI (uvicorn)    │ ──▶ │ Anthropic API    │
│ localhost:5173       │  (proxy)   │ localhost:8000       │     │ (Claude Sonnet)  │
│                      │ ◀───────── │                      │ ──▶ │ GitHub REST API  │
│                      │  JSON/text │                      │ ──▶ │ Voyage AI        │
└──────────┬───────────┘            └──────────┬───────────┘     └──────────────────┘
           │ GET /user (direct)                │
           ▼                                   ├──▶ Chroma (data/chroma, on disk)
     api.github.com                            └──▶ Postgres (job state, via SQLAlchemy async)
```

---

## 2. Tech Stack & Why

### Backend: Python 3.12, FastAPI, Anthropic SDK

| Choice | Why |
|---|---|
| **Python 3.12** | Python has the best AI/ML SDKs, and Anthropic, Voyage and Chroma all ship first-class Python clients. 3.12 gives modern typing (`Self`, `X \| None`, `type` aliases), which mypy strict mode relies on. |
| **FastAPI** | It is async-native, and nearly all of our work is waiting on I/O (LLM calls, GitHub, embeddings). Pydantic v2 validation is built in, so request contracts live in models and not in route bodies. `StreamingResponse` makes token streaming trivial. OpenAPI docs come for free at `/docs`. |
| **Anthropic SDK (`AsyncAnthropic`)** | Official client with typed streaming (`messages.stream`), tool use, prompt caching and typed errors (`RateLimitError`, `APIError`), which we map to domain exceptions. We use the async client only, so a slow review never blocks the event loop. |
| **Postgres + SQLAlchemy 2 (async, `asyncpg`) + Alembic** | Durable, shared home for job state (§3.8). Postgres is the default relational choice and its partial unique indexes enforce "one active job per repo" in the database itself. SQLAlchemy's async engine keeps DB I/O off the event loop like every other call; Alembic versions the schema. |
| **httpx (`AsyncClient`)** | Used for every outbound HTTP call. Its `MockTransport` lets service tests run without the network. |
| **conda** | One reproducible env (`code-roaster`) for runtime, lint, type and test tools. |

### Frontend: React, Vite, TypeScript, Tailwind, React Query

| Choice | Why |
|---|---|
| **React 19** | Component model fits a UI made of small, independent panels (input, stream, result, auth badge). It has the largest ecosystem, including `react-error-boundary` and Testing Library. |
| **Vite** | Near-instant dev server and HMR. Its `/api` proxy (`vite.config.ts`) makes the backend same-origin in dev, so there is no CORS friction while developing. |
| **TypeScript (strict, no `any`)** | The UI renders AI output, which is untrusted by nature. Strict types plus **Zod** runtime validation at the API boundary stop a malformed response from crashing a component deep in the tree. |
| **Tailwind CSS v4** | Utility classes keep styling next to markup and remove the naming overhead of custom CSS. The design system is small (dark theme, severity colours), so this is enough. |
| **React Query (TanStack v5)** | It owns all server state (loading, error, data, reset), so components never hand-roll `useState` for request lifecycles. Mutations match our "submit, get result" interactions. |

### AI: Claude Sonnet, Voyage AI (`voyage-code-3`), Chroma

| Choice | Why |
|---|---|
| **Claude Sonnet (`claude-sonnet-4-6`)** | Strong code reasoning at a cost and latency that suit an interactive tool. Its reliable **tool use** is what makes structured output possible: we force a `submit_code_review` tool call rather than parsing prose. The model ID lives in one constant (`ANTHROPIC_MODEL`). |
| **Prompt caching** | Every system prompt carries `cache_control: ephemeral`. The prompts are long, identical across requests, and sent on every review, so caching them is the cheapest cost win. |
| **Voyage AI `voyage-code-3`** | An embedding model trained specifically for code retrieval, which beats general-purpose text embeddings at matching code to code and natural language to code. Documents and queries are embedded with separate `input_type`s in one shared vector space. Anthropic has no embeddings API and recommends Voyage. |
| **Chroma** | An embedded, file-backed vector DB (`PersistentClient` → `data/chroma`). Zero infrastructure for local dev: no server, no Docker, no account. One collection per repo keeps indexes isolated. It is behind `VectorStore`, so swapping to a hosted store later touches one file. |

### Auth: GitHub OAuth

| Choice | Why |
|---|---|
| **GitHub OAuth (web flow, `repo` scope)** | The PR and repo features need to read the user's code, including private repos. Users already have a GitHub account, so there are no passwords to store and no user table. The `repo` scope is what private-repo diff and file access requires. |

**How it works:**

1. `GET /auth/github` generates a random `state`, stores it in a short-lived HttpOnly cookie scoped to `/auth/github`, and redirects to GitHub with it.
2. The callback rejects the request (401) unless the returned `state` matches the cookie, which blocks login CSRF. It then exchanges the code for a token server-side, so the client secret never reaches the browser.
3. The backend redirects to `{frontend_url}/auth/callback#token=…`. Browsers never send the fragment to a server, so the token stays out of server logs and `Referer` headers.
4. The SPA reads the token from the fragment, stores it in `sessionStorage`, and strips it from the URL.
5. The token is sent in the request body for each PR review.

**Trade-off:** the backend is **stateless**, with no sessions or database (the state cookie is the only server-issued state, and it lives in the browser), but the token passes through a URL fragment and lives in browser storage. That is acceptable for local and dev use. Revisit it for deployment (see §6).

---

## 3. Architecture Decisions

### 3.1 Single exception handler (`AppError` hierarchy + MRO-based routing)

**Decision:** every modelled failure subclasses `AppError` (`app/exceptions.py`). Each class declares its own `status_code`, `log_level` and optional `user_message`. `main.py` registers **one** handler on `AppError`. Because FastAPI resolves handlers by walking the exception's MRO, that single handler catches every subclass. A second handler, on `Exception`, is the backstop for real bugs: it always logs at ERROR and always returns a generic 500.

```
AppError
├── ReviewError
│   ├── AIProviderError            502 (hidden message)
│   │   └── AIProviderRateLimitError  429
│   └── MalformedAIResponseError   500 (hidden message)
├── GitHubError                    502 (hidden message)
│   ├── InvalidPRUrlError / InvalidRepoUrlError   400
│   ├── GitHubAuthError                           401
│   ├── PRNotFoundError / RepoNotFoundError       404
│   └── GitHubRateLimitError                      429
└── VectorStoreError               500 (hidden message)
```

**Why:**

- **A new failure mode is just a new class.** `main.py` never changes.
- **Logging and HTTP translation happen in exactly one place.** Services and routes only `raise`. They never catch, log, or build responses. This removes duplicate logs and inconsistent error shapes.
- **The exposure policy is declarative.** Expected, user-fixable errors show their message. Infra failures hide it behind `user_message`. `debug_context` is logged but never sent to the client.
- **Services own translation.** They map external failures, such as an HTTP status (`raise_for_github_response`) or an SDK error, to the right subclass. Raw `httpx`/SDK exceptions never reach a route.

**Known exception:** streaming (`CodeReviewer.review_stream`) logs inline before re-raising. Once bytes have been sent, the central handler can no longer send a clean JSON error.

Full rules: `app/CLAUDE.md` → *Error Handling*.

### 3.2 Pydantic Settings for config (fail fast)

**Decision:** all configuration is a typed field on `Settings` (`app/config.py`), loaded once from env and `.env`. Nothing else in `app/` reads `os.environ`.

**Why:**

- **Fail at import, not at first use.** Required keys (`anthropic_api_key`, `voyage_api_key`, `github_client_id`, `github_client_secret`, `database_url`) have no defaults, so a missing one stops the app at startup with a clear validation error. Without this, it would surface later as a 500 halfway through a review.
- **One inventory of config.** Values are typed and discoverable in one place. `.env.example` documents them.

### 3.3 DTO mapping layer (snake_case wire → camelCase domain)

**Decision:** the backend speaks idiomatic Python (snake_case) on the wire. The frontend keeps two shapes per feature:

- a `*DTO` type, inferred from a Zod schema, matching the wire;
- a camelCase domain type (e.g. `ReviewData`).

A `mapTo<Domain>` function in `src/api/` converts one to the other.

```
fetch → httpClient (HTTP errors → AppError) → Zod parse (DTO) → mapToReviewData → ReviewData
                                                 └──── never leaves src/api/ ────┘
```

**Why:**

- Each side stays idiomatic. There is no alias config on Pydantic models and no snake_case leaking into components.
- **Hooks and components only ever see validated, mapped data.** Backend renames are absorbed in one mapper, not across the UI.
- One mapper per domain is reused across endpoints. `/review/structured` and `/review/pr` both go through `mapToReviewData`, which maps each finding with `mapToFinding`.

The backend mirrors this in reverse. `CodeReviewer` returns a domain `StructuredReview`, and routes convert it with `StructuredReviewResponse.from_domain(...)`. This keeps the AI layer decoupled from the HTTP contract.

### 3.4 Two-phase review UX (stream first, then structured render)

**Decision:** a pasted-code review makes **two** Claude calls, in sequence (`useReview.submitReview`):

1. `POST /review/stream` streams a prose review as `text/plain` and renders it live (`StreamingText`).
2. When the stream finishes, `POST /review/structured` forces the `submit_code_review` tool call and returns JSON. That JSON replaces the stream with the rich result view (`ReviewResult`).

**Why:**

- **Perceived latency.** A structured tool call returns nothing until it is complete. Streaming shows useful output within a second or two.
- **Reliable structure.** Parsing structure out of streamed prose is fragile. A forced tool call with a JSON schema is dependable, and missing required fields raise `MalformedAIResponseError`.

**Trade-offs:**

- About 2× token cost per review. Prompt caching limits the input side.
- The two calls can disagree in wording.
- Total wall time is longer than a single call.

PR reviews use only the structured call, because diffs are reviewed as a batch.

An `AbortController` cancels an in-flight stream when a new review is submitted.

### 3.5 RAG pipeline design (chunker → embedder → vector store → indexer / retriever)

**Decision:** four single-responsibility services, each wrapping one concern, plus an orchestrator for each phase: `RepoIndexer` writes the index, `CodeRetriever` reads it. All of them exchange one type, `Chunk` (a frozen dataclass: `content`, `file_path`, `start_line`, `end_line`, `language`).

| Stage | Service | Responsibility |
|---|---|---|
| Fetch | `GitHubService.fetch_repo_files` | Default-branch tree, filtered to supported extensions, decoded as UTF-8 |
| Chunk | `CodeChunker` | Split each file along definition boundaries (regex-based), with a fixed-window fallback |
| Embed | `Embedder` | Chunks → `voyage-code-3` vectors, in batches of 128 |
| Store | `VectorStore` | Upsert into and search a per-repo Chroma collection |
| Orchestrate | `RepoIndexer` | Run fetch → chunk → embed → store and return an `IndexingResult` |
| Retrieve | `CodeRetriever` | Embed a query and return the top `k` chunks from a repo's collection; `[]` when there is no index or embedding fails |

**Why:**

- **Each stage is swappable and testable in isolation.** The external clients (Voyage, Chroma, `httpx`) are injected, so tests never hit the network. Replacing Chroma with a hosted store, or regex chunking with tree-sitter, touches one file.
- **One shared data type** means no adapters between stages. The rule is: extend `Chunk`, never add a parallel "snippet" type.
- **`RepoIndexer` and `CodeRetriever` take every dependency explicitly** (no defaults), so the pipeline is assembled in one visible place (the `lifespan`), with one shared `Embedder`.
- **Retrieval is never done inside the reviewer.** `CodeReviewer` receives an optional `CodeRetriever` and only consumes its chunks; it never touches `Embedder` or `VectorStore`. This keeps the reviewer to one job (calling the LLM) and makes retrieval a standalone callable, which V5 agents need as a tool (§6).
- **Definition-aligned chunks** (≤100 lines; fallback of 50-line windows with 10 lines of overlap; chunks under 5 lines dropped) keep each retrieved result a coherent unit, such as a function or class, not an arbitrary slice.

Details and thresholds: §5 and `app/CLAUDE.md` → *RAG Pipeline*.

### 3.6 Background tasks for indexing

**Decision:** `POST /index/repo` returns `202` immediately and runs `RepoIndexer.index_repository` as a **background task** (`run_indexing_job`). Clients poll `GET /index/status/{repo_id}`.

**Why:** indexing a repo means many GitHub requests, one embedding request per 128 chunks, and disk writes. That takes anywhere from seconds to minutes, which is far beyond what an HTTP request should hold open. Blocking would cause proxy timeouts, a frozen UI, and a lost result if the client disconnects.

**Starting point:** FastAPI's `BackgroundTasks`, which runs in-process after the response is sent and needs no extra infrastructure. Job **state** is persisted in Postgres (§3.8); only the **execution** is in-process.

**Known limits:**

- A restart kills in-flight jobs. On startup, `fail_orphaned_indexing_jobs` marks every `pending`/`running` job not updated for `INDEXING_JOB_TIMEOUT_SECONDS` (30 min) as `failed` with `error = "Server restarted"`, so the repo can be re-indexed. The timeout keeps a restarting worker from sweeping a job still alive on another worker. The cost: a repo whose job was killed stays blocked (`409`) for up to 30 minutes after the restart.
- `updated_at` only moves when a stage starts, so a single stage running longer than the timeout would be swept by a restarting worker. The swept job's runner would still write `completed` over the `failed` when it finishes.
- Jobs share the web worker's resources.

If these start to hurt (see §6), move execution to a real job queue; the `indexing_jobs` table stays as is.

### 3.7 Review response contract (`/review/*`): structured `Finding` objects

**Decision:** `POST /review/structured` and `POST /review/pr` return the same `StructuredReviewResponse`. A review job (§3.9) stores the same shape in `reviews.result` and sends it as its `completed` event:

| Field | Type |
|---|---|
| `detected_language` | `str` |
| `summary` | `str` |
| `severity` | `low` / `medium` / `high` / `critical` |
| `score` | `int`, 1–10 |
| `bugs`, `security_issues`, `suggestions`, `positives` | `list[Finding]`, possibly empty |

Every item in those four lists is a `Finding` (`app/models/review.py`):

| Field | Type | Set by | Notes |
|---|---|---|---|
| `id` | `str` (UUID4) | **Server** | Generated when the finding is built. It gives each finding a stable handle for agents, PR comments and evals. |
| `category` | `bug` / `security` / `suggestion` / `positive` | **Server** | Derived from the list Claude submitted the finding in. |
| `severity` | `low`…`critical`, or `null` | Claude | Left out for positives. |
| `file` | `str` or `null` | Claude | The path as it appears in the diff. `null` for pasted snippets or findings not tied to one file. |
| `line_start`, `line_end` | `int` ≥ 1, or `null` | Claude | New-file line numbers for a diff, snippet line numbers for pasted code. |
| `title` | `str` | Claude | A one-line headline. Required. |
| `explanation` | `str` | Claude | Why the finding matters. Required. |
| `suggestion` | `str` or `null` | Claude | A concrete fix, when there is one. |
| `confidence` | `low` / `medium` / `high` | Claude | How sure Claude is that the finding is correct. Required. |

**How a finding flows through the system:**

```
submit_code_review tool call: four arrays of finding objects (no id, no category)
   ▼  CodeReviewer: tag each item with its array's category; Finding.model_validate generates the id
   │    invalid item (missing field, wrong type, plain string) → MalformedAIResponseError
   ▼  StructuredReview (domain) → StructuredReviewResponse.from_domain → JSON (absent fields → null)
   ▼  Frontend: FindingSchema (Zod) → mapToFinding → Finding { lineStart, lineEnd, … }
   ▼  Section renders title, location (file:12-14 · file:12 · Line 3 · file), explanation
```

**Why:**

- **Plain strings were a dead end.** An agent can't act on a sentence, and a sentence can't become an inline PR comment. You also can't measure recall or false-positive rates on free text. File, line range, category and confidence make each finding addressable and measurable.
- **The server owns `id` and `category`, never Claude.** If Claude produced a category, it could contradict the list the finding sits in. If Claude produced an ID, it could be duplicated, malformed or reused across runs. Deriving both on the server makes them correct by construction. That's why the tool schema doesn't include them.
- **Strict validation, same failure path.** Every finding goes through Pydantic, so a malformed one fails through the existing `MalformedAIResponseError` path (§3.1). It never reaches the client half-formed.

**Trade-offs:**

- **One invalid finding fails the whole review.** Claude has been seen omitting required tool fields (see the TODO in `reviewer.py`), so check this rate with a live test.
- **Line numbers are inferred by Claude** and aren't checked against the diff yet. Treat them as best-effort until something validates them.
- **The category is stored twice:** implied by the list a finding is in, and explicit on the finding. The explicit field keeps a finding self-describing once it leaves its list, for example as an agent tool result or a PR comment.

Conventions: `app/CLAUDE.md` → *Review Findings*, `frontend/claude-docs/data-layer.md` → *Review Findings*.

### 3.8 Postgres for all job state (SQLAlchemy async + Alembic)

**Decision:** every piece of job state — indexing and review jobs today, agent runs in V5 — lives in **Postgres**, **never in process memory** (`app.state`, module globals, caches). Each job is a row; services read and write it through an `AsyncSession`.

**Why:**

- **Survives restarts.** The previous `dict` on `app.state` lost every job's status on reload.
- **Works with more than one worker.** Every process sees the same rows. The rule "one active indexing job per repo" is a partial unique index (`uq_indexing_jobs_active_repo_id`), so two workers racing on one repo can't both start it — the loser's `INSERT` fails and becomes a `409`.
- **History for free.** Re-indexing adds a row instead of overwriting one; the status endpoint returns the newest.
- **One pattern for V5.** Agent runs need the same create → update progress → record outcome lifecycle.

**How it is wired:**

- `app/database.py` owns the async engine, `SessionFactory`, `Base` and the `get_db` dependency (`DbSession`). ORM tables live in `app/models/db/`, apart from the Pydantic API models, and services map rows to response models.
- The `lifespan` calls `init_db()` and puts `SessionFactory` on `app.state.session_factory`. Background tasks receive it explicitly and open their own short sessions, because the request's session is closed by the time they run.
- **Schema:** startup runs `alembic upgrade head` in every environment, so a database is always exactly what the migrations define. There is no `create_all` shortcut, because it never alters existing tables and silently drifts from the migrations. Migrations live in `app/migrations/versions/`.
- **Orphaned jobs:** right after migrating, the lifespan calls `fail_orphaned_indexing_jobs` (§3.6) and `fail_orphaned_review_jobs` (§3.9).

**Trade-offs:**

- A Postgres server is now required to run the backend, and to run the DB-backed tests (`TEST_DATABASE_URL`).
- Every model change needs a migration before the app will see it, including in development.

Conventions: `app/CLAUDE.md` → *Database*.

### 3.9 Reviews as jobs, streamed over SSE

**Decision:** alongside the synchronous `POST /review/pr` (kept unchanged), a PR review can run as a **job**. `POST /review/pr/async` takes the same `PRReviewRequest`, records a `reviews` row and returns `202 {"job_id": ...}`; `run_review_job` then runs as a background task. The client follows the job with **Server-Sent Events** on `GET /review/pr/{job_id}/events`.

**Why:** a synchronous request holds the connection open until Claude answers. That is fine for one call of a few seconds, but V5 agent loops run for minutes. Proxies time out, the UI shows nothing in the meantime, and a dropped connection loses the result. A job decouples the run from the request. SSE (rather than polling a status endpoint, as indexing does) pushes each step as it happens. That matters once an agent has many steps to show. SSE is one-way, plain HTTP, and the browser's `EventSource` reconnects on its own.

**How it is wired:**

- **Two tables** (`app/models/db/review.py`):
  - `reviews`: one row per job. Columns: `id`, `repo_id`, `pr_url`, `state` (`pending` → `running` → `completed` / `failed`), `result` (JSONB, the full `StructuredReviewResponse`), `error`, `created_at`, `updated_at`.
  - `review_events`: an append-only log. Columns: `id` (a global sequence), `review_id`, `type`, `data` (JSONB), `created_at`.
- **The runner writes, the stream reads, and Postgres sits between them.** `run_review_job` appends an event at each step. A state change and its event are committed in one transaction. `stream_review_events` polls the log every 0.5 s for events newer than the last one it sent. Nothing passes through process memory (§3.8), so a client can follow a job running on another worker.
- **Replay and resume.** Each SSE message carries `id: <event id>`. A new subscriber gets every event from the start. A reconnecting `EventSource` sends `Last-Event-ID` and resumes after it. The stream ends after the terminal event, or straight away if the job already finished and nothing newer exists.
- **Access check before retrieval.** The route parses the PR URL (bad URL → `400` before any job is created) and derives `repo_id` from it, never from the client. The job fetches the diff with the caller's token **before** it retrieves any context, so the guarantee of `POST /review/pr` holds (§5.2). The GitHub token is passed to the background task and never stored.
- **Progress comes from the reviewer.** `CodeReviewer.review_pr_with_context` takes an optional `on_stage` callback, the same pattern as `RepoIndexer`. The job turns each `ReviewStage` into an event.
- **No pooled connection held by a stream.** The SSE route checks that the job exists with `FunctionScopedDbSession`, which closes before the body starts streaming. An unknown ID becomes a normal JSON `404`. Each poll then opens its own short session. FastAPI's `EventSourceResponse` sends a keep-alive comment every 15 s while no events arrive.

**SSE event types.** Each message's `data:` is JSON `{"id": int, "type": ..., "data": ...}` (`ReviewEventMessage`). No `event:` field is set, so `EventSource.onmessage` receives every type.

| `type` | When | `data` |
|---|---|---|
| `retrieving` | Retrieval of indexed context starts (skipped when no retriever is configured) | `null` |
| `reviewing` | The Claude review call starts | `null` |
| `finding` | Once per finding, after the review returns: bugs, then security issues, suggestions, positives | a `Finding` (§3.7) |
| `completed` | **Terminal.** The job succeeded | the full `StructuredReviewResponse` |
| `failed` | **Terminal.** The job failed, or was swept as orphaned | `{"error": "<client-safe message>"}` |

Every job ends with exactly one terminal event. Failures follow the `run_indexing_job` rules: an `AppError` records its `client_message`, and anything else records `"Internal server error"`.

**Built for agent steps.** `review_events.type` is a plain string column, not a Postgres enum, so a new `ReviewEventType` (e.g. `tool_call`, `tool_result`) needs no migration. An agent loop appends events the same way. Today `finding` events arrive in one burst, because the single Claude call returns every finding at once. An agent would emit each one as it finds it.

**Known limits:**

- **Same execution model as indexing (§3.6).** The job runs in-process, so a restart kills it. On startup, `fail_orphaned_review_jobs` marks `pending`/`running` jobs not updated for `REVIEW_JOB_TIMEOUT_SECONDS` (30 min) as `failed` and appends their `failed` event. Every event bumps `updated_at`, so a runner that keeps emitting events is never swept. A single step longer than 30 minutes would be swept, though.
- **Polling, not push.** Events reach the client up to 0.5 s late, and each open stream runs one small query per poll. `LISTEN/NOTIFY` is the upgrade path if many streams are open at once.
- **Clients must `close()` the `EventSource` on `completed`/`failed`.** Otherwise the browser reconnects after the stream ends. Each reconnect gets an empty stream that closes at once, so it is wasteful but harmless.
- **No job listing, cancellation or retention** yet. Rows and events are kept forever.

Conventions: `app/CLAUDE.md` → *Database* and *Review jobs*.

---

## 4. System Components

### 4.1 Backend: routes → services → external APIs

```
main.py (lifespan: builds singletons on app.state; the AppError handler and the Exception backstop)
│
├── routes/review.py   POST /review/stream       ─┐
│                      POST /review/structured    ├─▶ CodeReviewer ──────▶ Anthropic API
├── routes/pr.py       POST /review/pr           ─┘        │
│                        │                                 └─▶ CodeRetriever ─▶ Embedder ─▶ Voyage AI
│                        │                                                   ─▶ VectorStore ─▶ Chroma
│                        └─ GitHubService.parse_pr_url / fetch_pr_diff ──▶ GitHub REST API
├── routes/auth.py     GET  /auth/github          ─┐
│                      GET  /auth/github/callback ─┴▶ GitHubService.exchange_code_for_token
└── routes/health.py   GET  /health

routes/pr.py     POST /review/pr/async        ─▶ create_review_job ─────▶ Postgres (reviews)
                 GET  /review/pr/{id}/events  ─▶ stream_review_events ──▶ Postgres (review_events, polled) ─▶ SSE
                 (background)                 ─▶ run_review_job ─▶ Postgres (state + events, one tx per step)
                                                                ─▶ GitHubService.fetch_pr_diff ─▶ GitHub
                                                                ─▶ CodeReviewer.review_pr_with_context(on_stage=…)

routes/index.py  POST /index/repo        ─▶ create_indexing_job ─────▶ Postgres (indexing_jobs)
                 GET  /index/status/{id} ─▶ get_latest_indexing_job ─▶ Postgres
                 (background)            ─▶ run_indexing_job ─▶ Postgres (progress, outcome)
                                                             ─▶ RepoIndexer
                                                                ─▶ GitHubService.fetch_repo_files ─▶ GitHub
                                                                ─▶ CodeChunker (pure)
                                                                ─▶ Embedder (shared with CodeRetriever) ─▶ Voyage AI
                                                                ─▶ VectorStore ─▶ Chroma (disk)
```

**Layering rules:**

- **Routes are thin.** They validate input through Pydantic models (`field_validator`), call services from `req.app.state`, and map the result to a response model. Routes contain no business logic, no `httpx`, and no `try`/`except`.
- **Services own every external call.** Anthropic, GitHub and Voyage are all wrapped in `app/services/`. Services translate failures into `AppError` subclasses and log token usage.
- **Singletons are created in the `lifespan`.** `CodeReviewer`, `CodeRetriever`, `RepoIndexer`, `GitHubService` and the DB `session_factory` live on `app.state` (services and factories only — never job state, see §3.8); one `Embedder` is shared by the indexer and the retriever. Tests replace them with `MagicMock(spec=...)` without patching imports.
- **Prompts and tool schemas** (`app/prompts/review.py`) are kept apart from the code that calls the model.
- **Constants** (`app/constants.py`) are the single source for model IDs, severities, and the extension-to-language map shared by fetch and index.

### 4.2 Frontend: components → hooks → api → backend

```
App.tsx (layout + mode tabs)
 ├── components/ (presentational: CodeInput, StreamingText, ReviewResult, PRReviewPanel, Header, …)
 │        ▲ props only
 ├── hooks/ (state + React Query)
 │     useReview       → streamReview, then fetchReview   (two-phase, §3.4)
 │     usePRReview     → fetchPRReview
 │     useGitHubAuth   → sessionStorage token, OAuth callback handling
 │     useGitHubUser   → fetchGitHubUser (direct to api.github.com)
 │     useCodeForm / usePRForm → form state
 │        ▼
 ├── api/ (plain async functions: validate with Zod, map DTO → domain)
 │        ▼
 └── utils/httpClient (fetch wrapper: post / get / stream, HTTP status → typed AppError)
          ▼
     /api/*  ── Vite proxy (strips /api) ──▶  FastAPI :8000
```

**Rules:**

- **Components never fetch.** Hooks never see DTOs. The `api/` functions contain no React code.
- **Errors take one path.** `httpClient` turns every failure into a frontend `AppError` with a code (`RateLimitError`, `ValidationError`, `ApiError`). Components render these through `ErrorMessage`. `ErrorBoundary` wraps each panel and the root, so a render crash stays contained.
- **The GitHub profile is fetched straight from GitHub** with the user's token, so the backend does not need a proxy endpoint just for the avatar and username.

---

## 5. RAG Pipeline

**Goal:** give the reviewer knowledge of the repository beyond the diff or snippet, such as how a changed function is called, what conventions the codebase follows, and which helpers already exist. Reviews can then flag misuse and duplication, not only local bugs.

### 5.1 Index phase *(implemented; exposed via `POST /index/repo`)*

```
repo_url + github_token
   │
   ▼  GitHubService.fetch_repo_files
   │    default branch → recursive tree → keep SUPPORTED_CODE_EXTENSIONS → fetch blobs → decode UTF-8 (binary skipped)
   ▼  RepoIndexer
   │    skip files > MAX_INDEXABLE_FILE_LINES (500)
   │    extension → language via EXTENSION_TO_LANGUAGE (unknown extensions are skipped defensively)
   ▼  CodeChunker.chunk_file
   │    split at function/class definitions → merge neighbours up to 100 lines
   │    oversized definitions / files without definitions → 50-line windows, 10-line overlap
   │    drop chunks < 5 lines
   ▼  Embedder.embed_chunks
   │    voyage-code-3, input_type="document", batches of 128
   ▼  VectorStore.delete_collection
   │    drop the previous run's chunks
   ▼  VectorStore.add_chunks
        Chroma collection per repo; id = "{file_path}:{start_line}:{end_line}"
        upserted in batches of client.get_max_batch_size()
        metadata: file_path, start_line, end_line, language
   ▼
IndexingResult(files_processed, chunks_created, chunks_stored, duration_seconds)
```

- **Supported languages:** Python, TypeScript, JavaScript, Go, Rust, Java.
- **Re-indexing:** `RepoIndexer` calls `VectorStore.delete_collection()` at the start of the store stage, so chunks from deleted or renamed files don't linger. Upserts alone would only overwrite matching IDs.
- **Chroma calls:** the Chroma client is synchronous, so every `VectorStore` call runs in `asyncio.to_thread`. Chroma failures, including its bare `ValueError` on an oversized batch, are raised as `VectorStoreError`.

### 5.2 Retrieval phase *(implemented in `CodeRetriever`; used by `/review/pr`)*

```
review request (snippet or PR diff)
   ▼  CodeRetriever.retrieve(repo_id, query, k=5)
   │    VectorStore.collection_exists  no index → []
   │    Embedder.embed_query           voyage-code-3, input_type="query"; failure → logged, []
   │    VectorStore.search(k)          nearest chunks, most similar first → list[Chunk]
   ▼  CodeReviewer                  retrieved chunks injected as labelled context
                                    (file_path:start–end) alongside the code under review
```

Still open:

- how the query is built from a diff: the whole diff, or one query per hunk or per changed symbol;
- the token budget for retrieved context (see "never send more context than needed" in `app/CLAUDE.md`);
- how the review prompt cites retrieved code.

### 5.3 Why these choices

- **Voyage `voyage-code-3` for embeddings.** The model is specialised for code, and retrieval quality is the ceiling on RAG usefulness. The separate `document` and `query` input types matter here, because the query is a diff while the documents are whole definitions. Voyage is Anthropic's recommended embeddings provider, and it has an async client that fits the async stack.
- **Chroma for local dev.** It runs embedded, persists to `data/chroma` (gitignored, rebuildable), and needs no servers or accounts. That is the right weight while the retrieval design is still changing. The `VectorStore` wrapper exists so a hosted option (pgvector, a managed Chroma, etc.) can replace it at deployment without touching the other stages.
- **Regex chunking over AST parsing.** One pattern per language is simple and dependency-free, and it is good enough to align chunks with definitions. Tree-sitter is the upgrade path if chunk quality becomes the bottleneck.

---

## 6. What's Coming

| Version | Scope | Architectural impact |
|---|---|---|
| **V4 (in progress)** | RAG codebase indexing: an indexing endpoint using background tasks (§3.6) and retrieval-augmented reviews (§5.2). | New routes; `RepoIndexer`, `Embedder` and `VectorStore` wired into `lifespan`; the review prompt gains a context section. |
| **V5: Agents** | The reviewer moves from single-shot calls to an agent loop that decides for itself what to inspect, using tools such as search the index, read a file, or fetch related PRs. | `CodeReviewer` evolves into a tool-using agent. The RAG services become agent tools. Error handling and token logging must cover multi-step runs. Runs reuse the review-job pattern (§3.9): each agent step is a new `review_events` type, streamed over the existing SSE endpoint. |
| **V6: Deployment** | Production hosting. | Revisit: token transport and storage (§2 Auth); moving Chroma from local disk to a hosted vector store; moving `BackgroundTasks` to a durable job queue with heartbeats (job state is already in Postgres, §3.8; it would replace the timeout-based orphan sweep, §3.6); CORS and `frontend_url` per environment; secrets management beyond `.env`. |

---

## Keeping this document current

Update this file when you:

- add a service, route, or external dependency;
- change a decision recorded in §3;
- ship a "not yet wired" item.

Update `docs/architecture.excalidraw` at the same time for structural changes (root `CLAUDE.md` → *Documentation*).
