# Code Roaster — Architecture

> A living document. It explains **why** the system is shaped the way it is, not only what exists.
> Conventions and step-by-step "how to" rules live in `CLAUDE.md`, `app/CLAUDE.md` and `frontend/CLAUDE.md`. This file links to them instead of repeating them.
> Last reviewed: 2026-09-28 (branch `feature/rag-codebase-indexing`).

---

## 1. System Overview

Code Roaster is an AI code reviewer. There are two ways in:

- **Paste code:** submit a snippet and watch the review stream in, then get a structured result.
- **Review a pull request:** sign in with GitHub, paste a PR URL, and the backend fetches the diff and reviews it.

Either way, the output has the same structure: a **score (1–10)**, an overall **severity**, a **summary**, and lists of **bugs**, **security issues**, **suggestions** and **positives**.

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
           ▼                                   ▼
     api.github.com                     Chroma (data/chroma, on disk)
```

---

## 2. Tech Stack & Why

### Backend: Python 3.12, FastAPI, Anthropic SDK

| Choice | Why |
|---|---|
| **Python 3.12** | Python has the best AI/ML SDKs, and Anthropic, Voyage and Chroma all ship first-class Python clients. 3.12 gives modern typing (`Self`, `X \| None`, `type` aliases), which mypy strict mode relies on. |
| **FastAPI** | It is async-native, and nearly all of our work is waiting on I/O (LLM calls, GitHub, embeddings). Pydantic v2 validation is built in, so request contracts live in models and not in route bodies. `StreamingResponse` makes token streaming trivial. OpenAPI docs come for free at `/docs`. |
| **Anthropic SDK (`AsyncAnthropic`)** | Official client with typed streaming (`messages.stream`), tool use, prompt caching and typed errors (`RateLimitError`, `APIError`), which we map to domain exceptions. We use the async client only, so a slow review never blocks the event loop. |
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

1. `GET /auth/github` redirects to GitHub.
2. The callback exchanges the code for a token server-side, so the client secret never reaches the browser.
3. The backend redirects to `{frontend_url}/auth/callback?token=…`.
4. The SPA stores the token in `sessionStorage` and strips it from the URL.
5. The token is sent in the request body for each PR review.

**Trade-off:** the backend is **stateless**, with no sessions or database, but the token passes through a URL and lives in browser storage. That is acceptable for local and dev use. Revisit it for deployment (see §6).

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
└── GitHubError                    502 (hidden message)
    ├── InvalidPRUrlError / InvalidRepoUrlError   400
    ├── GitHubAuthError                           401
    ├── PRNotFoundError / RepoNotFoundError       404
    └── GitHubRateLimitError                      429
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

- **Fail at import, not at first use.** Required keys (`anthropic_api_key`, `voyage_api_key`, `github_client_id`, `github_client_secret`) have no defaults, so a missing one stops the app at startup with a clear validation error. Without this, it would surface later as a 500 halfway through a review.
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
- One mapper per domain is reused across endpoints. `/review/structured` and `/review/pr` both go through `mapToReviewData`.

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

### 3.5 RAG pipeline design (chunker → embedder → vector store → indexer)

**Decision:** four single-responsibility services, each wrapping one concern, plus an orchestrator. All of them exchange one type, `Chunk` (a frozen dataclass: `content`, `file_path`, `start_line`, `end_line`, `language`).

| Stage | Service | Responsibility |
|---|---|---|
| Fetch | `GitHubService.fetch_repo_files` | Default-branch tree, filtered to supported extensions, decoded as UTF-8 |
| Chunk | `CodeChunker` | Split each file along definition boundaries (regex-based), with a fixed-window fallback |
| Embed | `Embedder` | Chunks → `voyage-code-3` vectors, in batches of 128 |
| Store | `VectorStore` | Upsert into and search a per-repo Chroma collection |
| Orchestrate | `RepoIndexer` | Run fetch → chunk → embed → store and return an `IndexingResult` |

**Why:**

- **Each stage is swappable and testable in isolation.** The external clients (Voyage, Chroma, `httpx`) are injected, so tests never hit the network. Replacing Chroma with a hosted store, or regex chunking with tree-sitter, touches one file.
- **One shared data type** means no adapters between stages. The rule is: extend `Chunk`, never add a parallel "snippet" type.
- **`RepoIndexer` takes every dependency explicitly** (no defaults), so the pipeline is assembled in one visible place.
- **Definition-aligned chunks** (≤100 lines; fallback of 50-line windows with 10 lines of overlap; chunks under 5 lines dropped) keep each retrieved result a coherent unit, such as a function or class, not an arbitrary slice.

Details and thresholds: §5 and `app/CLAUDE.md` → *RAG Pipeline*.

### 3.6 Background tasks for indexing *(decided, not yet wired)*

**Decision:** indexing will be started by an endpoint that returns immediately and runs `RepoIndexer.index_repository` as a **background task**.

**Why:** indexing a repo means many GitHub requests, one embedding request per 128 chunks, and disk writes. That takes anywhere from seconds to minutes, which is far beyond what an HTTP request should hold open. Blocking would cause proxy timeouts, a frozen UI, and a lost result if the client disconnects.

**Starting point:** FastAPI's `BackgroundTasks`, which runs in-process after the response is sent and needs no extra infrastructure.

**Known limits:**

- No persistence. A server restart loses in-flight jobs.
- No built-in progress reporting. The client will need a status or poll endpoint, which can use `VectorStore.collection_exists`.
- Jobs share the web worker's resources.

If any of these start to hurt (see §6), move to a real job queue.

**Status:** `RepoIndexer` exists and is tested. No route calls it yet, and there is no `BackgroundTasks` usage in `app/` today.

---

## 4. System Components

### 4.1 Backend: routes → services → external APIs

```
main.py (lifespan: builds singletons on app.state; the AppError handler and the Exception backstop)
│
├── routes/review.py   POST /review/stream       ─┐
│                      POST /review/structured    ├─▶ CodeReviewer ──────▶ Anthropic API
├── routes/pr.py       POST /review/pr           ─┤        ▲
│                        └─ GitHubService.parse_pr_url / fetch_pr_diff ──▶ GitHub REST API
├── routes/auth.py     GET  /auth/github          ─┐
│                      GET  /auth/github/callback ─┴▶ GitHubService.exchange_code_for_token
└── routes/health.py   GET  /health

(not yet routed)  RepoIndexer ─▶ GitHubService.fetch_repo_files ─▶ GitHub
                              ─▶ CodeChunker (pure)
                              ─▶ Embedder ─────────────────────────▶ Voyage AI
                              ─▶ VectorStore ──────────────────────▶ Chroma (disk)
```

**Layering rules:**

- **Routes are thin.** They validate input through Pydantic models (`field_validator`), call services from `req.app.state`, and map the result to a response model. Routes contain no business logic, no `httpx`, and no `try`/`except`.
- **Services own every external call.** Anthropic, GitHub and Voyage are all wrapped in `app/services/`. Services translate failures into `AppError` subclasses and log token usage.
- **Singletons are created in the `lifespan`.** `CodeReviewer` and `GitHubService` live on `app.state`, so tests replace them with `MagicMock(spec=...)` without patching imports.
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

### 5.1 Index phase *(implemented; entry point not yet exposed)*

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
   ▼  VectorStore.add_chunks
        Chroma collection per repo; id = "{file_path}:{start_line}:{end_line}" (upsert → idempotent re-index)
        metadata: file_path, start_line, end_line, language
   ▼
IndexingResult(files_processed, chunks_created, chunks_stored, duration_seconds)
```

- **Supported languages:** Python, TypeScript, JavaScript, Go, Rust, Java.
- **Re-indexing:** call `VectorStore.delete_collection()` first to drop chunks from deleted or renamed files. Upserts alone only overwrite matching IDs.

### 5.2 Retrieval phase *(building blocks exist; not yet used by reviews)*

```
review request (snippet or PR diff)
   ▼  Embedder.embed_query          voyage-code-3, input_type="query"
   ▼  VectorStore.search(n=5)       nearest chunks, most similar first → list[Chunk]
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
| **V5: Agents** | The reviewer moves from single-shot calls to an agent loop that decides for itself what to inspect, using tools such as search the index, read a file, or fetch related PRs. | `CodeReviewer` evolves into a tool-using agent. The RAG services become agent tools. Error handling and token logging must cover multi-step runs. |
| **V6: Deployment** | Production hosting. | Revisit: token transport and storage (§2 Auth); moving Chroma from local disk to a hosted vector store; moving `BackgroundTasks` to a durable job queue; CORS and `frontend_url` per environment; secrets management beyond `.env`. |

---

## Keeping this document current

Update this file when you:

- add a service, route, or external dependency;
- change a decision recorded in §3;
- ship a "not yet wired" item.

Update `docs/architecture.excalidraw` at the same time for structural changes (root `CLAUDE.md` → *Documentation*).
