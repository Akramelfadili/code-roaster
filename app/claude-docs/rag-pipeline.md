# RAG Pipeline

Indexing embeds a repository's source; PR review retrieves relevant chunks as context.

| Stage | Class (`app/services/`) | Key facts |
|---|---|---|
| Fetch | `GitHubService.fetch_repo_files` (`github.py`) | Default-branch tree, filtered to `SUPPORTED_CODE_EXTENSIONS`; non-UTF-8 files skipped |
| Chunk | `CodeChunker` (`chunker.py`) | Definition-aligned, merged up to 100 lines; 50-line windows (10 overlap) fallback; chunks < 5 lines dropped |
| Embed | `Embedder` (`embedder.py`) | Voyage `voyage-code-3`, batches of 128; `document` vs `query` input types |
| Store | `VectorStore` (`vector_store.py`) | Persistent Chroma at `data/chroma` (gitignored), one collection per repo |
| Orchestrate | `RepoIndexer` (`indexer.py`) | Runs fetch → chunk → embed → store, awaits the async `on_stage` callback as each `IndexingStage` starts |
| Job | `create_indexing_job` / `get_latest_indexing_job` / `run_indexing_job` (`indexing_jobs.py`) | `POST /index/repo` → row in `indexing_jobs` + 202 + `BackgroundTasks`; `GET /index/status/{repo_id}` reads the newest row |
| Retrieve | `CodeRetriever.retrieve` (`retriever.py`) | Embeds the query, returns the top `k` (default 5) chunks; `[]` if the repo has no index or embedding fails |
| Augment | `ContextBuilder.build` (`context_builder.py`), called by `CodeReviewer.review_pr_with_context` | Asks `CodeRetriever` for chunks for the diff, fits them to `MAX_CONTEXT_CHARS`, formats them; the reviewer prepends them to the review message |

## Rules
1. **`Chunk` is the only unit passed between stages.** Extend or wrap it — never introduce a parallel "snippet"/"fragment" type
2. **Caller contract violations raise `ValueError`, not `AppError`** — e.g. an unsupported language in `CodeChunker`, or mismatched `chunks`/`embeddings` lengths in `VectorStore.add_chunks`
3. **Never accept `repo_id` from the client.** Derive it server-side as `{owner}__{repo}` lowercased (`REPO_ID_SEPARATOR`) from the parsed URL — and for `/review/pr` and review jobs (`run_review_job`), only use it after `fetch_pr_diff` succeeds with the caller's token. Otherwise anyone could pull another repo's chunks into their review. The repo ID is both the job key and the Chroma collection name
4. **Job state lives in Postgres** (`indexing_jobs`), never in memory — see `app/CLAUDE.md` → *Database*. One active job per repo, enforced by the partial unique index `uq_indexing_jobs_active_repo_id`: re-indexing while `pending`/`running` returns 409; a `completed`/`failed` job is kept as history and a new row is added. The GitHub token is never stored on the job. Execution is still in-process (`BackgroundTasks`), so a restart orphans running jobs. On startup, `fail_orphaned_indexing_jobs` fails those not updated for `INDEXING_JOB_TIMEOUT_SECONDS` (`error = "Server restarted"`)
5. **Fetch and index agree on "supported" via `EXTENSION_TO_LANGUAGE`.** `RepoIndexer` doesn't trust `GitHubService`'s filter: unknown extensions are skipped (fail soft, no `KeyError`), as are files over `MAX_INDEXABLE_FILE_LINES`
6. **Re-indexing is idempotent.** Vector IDs are `{file_path}:{start_line}:{end_line}`, so upserts overwrite; call `delete_collection()` before a full re-index
7. **Sync Chroma calls never block the event loop** — they run via `asyncio.to_thread`
8. **Context is optional.** `CodeRetriever.retrieve` returns `[]` when the collection is missing/empty or the query embedding fails (logged at WARNING); `review_pr_with_context` then falls back to `review_pr_diff`, as it does when no retriever is injected. `VectorStoreError` still propagates
9. **Retrieval never happens inside the reviewer.** `CodeReviewer` and `ContextBuilder` never touch `Embedder` or `VectorStore` — the reviewer receives a `CodeRetriever`, and `ContextBuilder` calls its `retrieve`. Any new consumer of codebase context (e.g. V5 agent tools) goes through `CodeRetriever` too
10. **One `Embedder`, explicit wiring.** `main.py`'s lifespan builds a single `Embedder` shared by `RepoIndexer` and `CodeRetriever`; both take `embedder` and `vector_store_factory` as required constructor args (no defaults), so tests inject fakes
