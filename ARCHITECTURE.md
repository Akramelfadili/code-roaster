# Code Roaster — Architecture

> Why the system is shaped the way it is. For *what* exists, read the code; for *how* to work in it, read `app/CLAUDE.md` and `frontend/CLAUDE.md`.

## 1. System Overview

Code Roaster is an AI code reviewer with two entry points: **paste code** (the review streams in live, then becomes a structured result) or **review a pull request** (sign in with GitHub, paste a PR URL, and the backend fetches the diff). Both produce the same output: a score, a severity, a summary, and four lists of structured **findings** (bugs, security issues, suggestions, positives).

The core value is feedback that is structured and consistent, so it is quick to act on and comparable across runs. It is also a learning project for AI engineering: each version adds one technique (streaming, tool use, OAuth, RAG, then agents), and the architecture is built to absorb the next one.

```
┌────────────────────┐  /api/* (Vite proxy)  ┌────────────────────┐ ──▶ Anthropic API (Claude Sonnet)
│ React SPA          │ ────────────────────▶ │ FastAPI            │ ──▶ GitHub REST API
│                    │ ◀──── JSON/text/SSE ─ │                    │ ──▶ Voyage AI (embeddings)
└─────────┬──────────┘                       └─────────┬──────────┘
          └──▶ api.github.com (profile only)           ├──▶ Chroma (vectors, on disk)
                                                       └──▶ Postgres (job state, daily spend)
```

## 2. Stack choices that shape the design

- **Async end to end (FastAPI, `AsyncAnthropic`, `httpx.AsyncClient`, SQLAlchemy async).** Nearly all work is waiting on I/O (LLM, GitHub, embeddings, DB), so nothing may block the event loop. Sync-only clients (Chroma) run in a thread.
- **Forced tool use for structure.** Claude Sonnet's reliable tool calling lets us force a `submit_code_review` call against a JSON schema instead of parsing prose.
- **Voyage `voyage-code-3` + Chroma.** Anthropic has no embeddings API and recommends Voyage; this model is trained for code retrieval. Chroma is embedded and file-backed: zero infrastructure while the retrieval design is still moving. It sits behind one wrapper so a hosted store can replace it.
- **Postgres.** The only durable, shared state (§3.8). Chosen over anything lighter because partial unique indexes let the database itself enforce invariants across workers.
- **GitHub OAuth, no user table.** Private-repo access needs the `repo` scope anyway, so GitHub is the identity. The token travels in a URL fragment (never sent to servers or `Referer`) and lives in `sessionStorage`; a `state` cookie blocks login CSRF. Acceptable for local use; revisit for deployment (§6).

## 3. Architecture Decisions

### 3.1 One exception hierarchy, one handler

Every modelled failure subclasses `AppError` and declares its own status, log level and whether its message is safe to show. FastAPI resolves handlers by walking the MRO, so **one** handler on `AppError` covers every subclass; a second on `Exception` is the backstop for real bugs (ERROR log, generic 500).

```
AppError
├── ReviewError
│   ├── AIProviderError              502 (hidden)
│   │   └── AIProviderRateLimitError 429
│   ├── MalformedAIResponseError     500 (hidden)
│   └── OutputTruncatedError         500
├── GitHubError                      502 (hidden)
│   ├── InvalidPRUrlError / InvalidRepoUrlError  400
│   ├── GitHubAuthError                          401
│   ├── PRNotFoundError / RepoNotFoundError      404
│   └── GitHubRateLimitError                     429
├── VectorStoreError                 500 (hidden)
│   Agent-run errors (V5):
├── ToolExecutionError               never reaches HTTP: returned to the model as an is_error tool_result
├── AgentStepLimitExceededError / BudgetExceededError           429
└── RunTimeoutError 504 / RunCancelledError 499 / ContextTooLargeError 413
```

**Why:** a new failure mode is a new class, and `main.py` never changes. Logging and HTTP translation live in exactly one place, so services and routes only `raise`: no duplicate logs, no inconsistent error shapes. Services translate raw SDK/HTTP errors at their edge, so routes never see them. Agent loops need typed failures to decide whether to recover (tool error) or end the run (everything else). **Exceptions to "only raise":** a stream that has already sent bytes can't become a JSON error, so it logs inline; background jobs have already returned `202`, so they catch and record the error on the job. Rules: `app/claude-docs/error-handling.md`.

### 3.2 Config fails fast

All config is one typed `Settings` object; required secrets have no defaults. A missing key stops the app at startup instead of surfacing as a 500 halfway through a review.

### 3.3 DTOs mapped at the API boundary, both directions

The wire is snake_case (idiomatic Python); the frontend domain is camelCase. Each frontend feature parses the wire shape with Zod and maps it once in `src/api/` (AI output is untrusted, so validation stops a malformed response from crashing a component deep in the tree); hooks and components only ever see validated domain types, so a backend rename is absorbed in one mapper. The backend mirrors this: the reviewer returns a domain object and routes convert it to the response model, keeping the AI layer independent of the HTTP contract.

### 3.4 Pasted code: stream first, then structure

A pasted review makes two Claude calls: a streamed prose review for perceived latency, then a forced tool call for reliable structure, which replaces the stream when it lands. A tool call returns nothing until complete, and parsing structure out of streamed prose is fragile, so we pay for both. **Trade-offs:** ~2× tokens (prompt caching limits the input side), longer total wall time, and the two outputs can disagree in wording. PR reviews skip the stream.

### 3.5 RAG as single-purpose stages sharing one type

Fetch → chunk → embed → store are separate services, orchestrated by an indexer (write side) and a retriever (read side). All stages exchange one `Chunk` type.

**Why:** each stage is swappable and testable alone (clients are injected, so tests never touch the network); swapping Chroma or regex chunking touches one file. One shared type means no adapters. **Retrieval never happens inside the reviewer:** the reviewer only consumes chunks, which keeps it to one job and makes retrieval a standalone callable that V5 agents can use as a tool. Details: §5.

### 3.6 Indexing runs as a background job

Indexing takes seconds to minutes (many GitHub requests, batched embeddings, disk writes), far longer than an HTTP request should stay open. `POST /index/repo` returns `202` and clients poll for status. Execution uses in-process `BackgroundTasks` (no extra infrastructure); **state** lives in Postgres (§3.8). **Known limits:** a restart kills in-flight jobs. On startup, jobs not updated for 30 minutes are marked failed; the timeout stops a restarting worker from sweeping a job still alive on another one, at the cost of a killed repo staying blocked for up to 30 minutes. A single stage longer than the timeout would be wrongly swept. The fix for all of this is a real job queue (§6); the table stays.

### 3.7 Findings are structured objects, not strings

Each finding carries a title, explanation, confidence and, when locatable, a file and line range (fields: `app/models/review.py`; rules: `app/CLAUDE.md` → *Review Findings*). **Why:** a sentence can't become an inline PR comment, can't be acted on by an agent, and can't be scored for recall or false positives. Location, category and confidence make each finding addressable and measurable.

- **The server owns `id` and `category`, never Claude.** A model-written category could contradict the list the finding sits in; a model-written ID could be duplicated or malformed. Both are derived server-side, so they are correct by construction, and the tool schema omits them.
- **Strict validation, existing failure path.** Every finding goes through Pydantic; a malformed one becomes `MalformedAIResponseError` and never reaches the client half-formed.

**Trade-offs:** one invalid finding fails the whole review (so new fields default to optional). Line numbers are inferred by Claude and not yet checked against the diff. Category is stored twice (list and field) so a finding stays self-describing once it leaves its list.

### 3.8 All job state in Postgres, never in memory

Indexing jobs, review jobs, future agent runs and the daily spend total live in Postgres, never in `app.state`, globals or caches.

**Why:** state survives restarts (the old in-memory dict didn't) and every worker sees the same rows. Invariants like "one active indexing job per repo" are a partial unique index, so two racing workers can't both start one; the loser gets a `409`. Re-runs add rows, giving history for free. Agent runs reuse the same create → progress → outcome lifecycle. **Schema is always `alembic upgrade head`,** in every environment, never `create_all`: `create_all` doesn't alter existing tables and silently drifts from the migrations. Cost: every model change needs a migration before even dev sees it, and a Postgres server is required (Docker Compose provides it locally).

### 3.9 Reviews as jobs, streamed over SSE

Alongside the synchronous PR review, a review can run as a job: `POST` returns `202 {job_id}`, and the client follows it over Server-Sent Events. **Why:** a single call of a few seconds can hold a request open; a V5 agent loop of several minutes can't (proxy timeouts, blank UI, result lost on disconnect). SSE over polling because an agent's steps should appear as they happen; it is one-way plain HTTP and `EventSource` reconnects on its own.

- **Postgres sits between the runner and the stream.** The runner appends to an event log, committing each state change with its event in one transaction; the stream polls the log. Nothing passes through memory, so any worker can serve any job's stream, and event IDs give replay and `Last-Event-ID` resume for free.
- **Event type is a plain string column,** not a Postgres enum, so a new agent step type needs no migration. Every job ends with exactly one terminal event (`completed` or `failed`).
- **Access is checked before retrieval.** `repo_id` is derived from the PR URL, never the client, and is only used after the diff fetch succeeds with the caller's token; otherwise anyone could pull another repo's indexed code into their review. The token is passed to the task, never stored.
- **Streams don't hold pooled connections.** Existence is checked with a session that closes before the body streams; each poll opens its own short session.
- **Stored results are versioned.** When the result shape changes incompatibly, older results read as `failed` ("schema outdated") instead of a validation `500`.

**Known limits:** same in-process execution and orphan sweep as §3.6 (every event bumps `updated_at`, so an active runner is never swept). Polling adds up to 0.5 s latency and one query per open stream; `LISTEN/NOTIFY` is the upgrade path. No listing, cancellation or retention yet. Event types and payloads: `app/CLAUDE.md` → *Review Jobs*.

### 3.10 Capped inputs and a daily cost budget

Uncapped endpoints let one request fill Claude's context, and V5 agents multiply calls per run, so one runaway run could drain the API balance. This was the biggest risk to close before V5.

- **Every LLM/embedding input has a character cap** (characters, not tokens: free to count, and ~3–4 chars/token keeps a worst-case PR review well inside the context window). **Reject what the client sends, truncate what the server builds:** an oversized request field is the user's to fix (`422`); an oversized diff or context isn't, so the review runs truncated, dropping the least relevant context first.
- **Every Claude and Voyage call is charged to a daily budget** stored in Postgres and incremented atomically, so it holds across workers. Once spend reaches the limit, calls raise `BudgetExceededError`.

**Trade-offs:** truncation is silent to the user (only a WARNING log). The budget is soft: a call's cost is known only after it returns, so in-flight calls can overshoot it, and a stream that fails midway isn't charged. Prices are hard-coded and need updating with the model. Caps and values: `app/CLAUDE.md` → *Input Caps & Cost Budget*.

## 4. Layers

### 4.1 Request flow

```
Frontend   components ──(props)── hooks (React Query) ── api/ (Zod parse + map) ── httpClient
                                                                                     │ /api/*
Backend    routes (thin: validate, call service, map response) ◀────────────────────┘
             │
             ├─▶ CodeReviewer (orchestrator) ─▶ ContextBuilder ─▶ CodeRetriever ─▶ Embedder / VectorStore
             │                               ─▶ ClaudeClient (every Claude call) ─▶ Anthropic
             │                               ─▶ ReviewParser (tool input → domain)
             ├─▶ GitHubService ─▶ GitHub
             ├─▶ review / indexing jobs (BackgroundTasks) ─▶ Postgres ─▶ SSE / status polling
             └─▶ RepoIndexer ─▶ GitHubService, CodeChunker, Embedder, VectorStore
```

- **Routes are thin; services own every external call.** This is what keeps error translation (§3.1) and cost accounting (§3.10) in one place each.
- **One door to Claude.** `ClaudeClient` does the budget check, error mapping, usage/cost logging and truncation check, so the V5 agent loop calling it directly inherits all of it.
- **Singletons are built once in the `lifespan`** and live on `app.state` (services only, never job state). Tests swap them for mocks without patching imports.
- **Frontend: components never fetch, hooks never see DTOs.** The GitHub profile is fetched straight from GitHub with the user's token, so the backend needs no proxy endpoint just for an avatar.

## 5. RAG Pipeline

**Goal:** let the reviewer see the repository beyond the diff (how a changed function is called, existing helpers, conventions), so it can flag misuse and duplication, not only local bugs.

- **Chunks align to definitions** (regex per language, with a fixed-window fallback) so each retrieved result is a coherent function or class, not an arbitrary slice. Regex over tree-sitter: dependency-free and good enough; tree-sitter is the upgrade path if chunk quality becomes the bottleneck.
- **Separate `document` and `query` embedding types,** because the query is a diff while the documents are whole definitions.
- **Re-indexing drops the collection first,** so chunks from deleted or renamed files don't linger (upserts alone only overwrite matching IDs).
- **Context is optional.** No index, or a failed query embedding, means the review runs on the diff alone rather than failing.

**Open questions:** how to build the query from a diff (whole diff, per hunk, per symbol); whether the character budget should become a token budget; how the prompt should cite retrieved code. Stage-level facts: `app/claude-docs/rag-pipeline.md`.

## 6. What's Coming

- **V5: Agents.** The reviewer becomes a tool-using loop that decides what to inspect (search the index, read a file, fetch related PRs). It is designed in already: retrieval is a standalone callable (§3.5), every Claude call goes through one client (§4.1), typed errors separate recoverable from run-ending (§3.1), the budget covers every call (§3.10), and each agent step becomes a new event type on the existing review-job SSE stream (§3.9).
- **V6: Deployment.** Revisit token transport and storage (§2); move Chroma to a hosted vector store; replace `BackgroundTasks` and the timeout-based orphan sweep with a durable queue with heartbeats (§3.6); per-environment CORS and secrets management beyond `.env`.
