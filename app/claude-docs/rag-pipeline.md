# RAG Pipeline

Indexing embeds a repository's source; PR review retrieves relevant chunks as context.

| Stage | Class (`app/services/`) | Key facts |
|---|---|---|
| Fetch | `GitHubService.fetch_repo_files` (`github.py`) | Default-branch tree, filtered to `SUPPORTED_CODE_EXTENSIONS`; non-UTF-8 files skipped |
| Chunk | `CodeChunker` (`chunker.py`) | Definition-aligned, merged up to 100 lines; 50-line windows (10 overlap) fallback; chunks < 5 lines dropped |
| Embed | `Embedder` (`embedder.py`) | Voyage `voyage-code-3`, batches of 128; `document` vs `query` input types |
| Store | `VectorStore` (`vector_store.py`) | Persistent Chroma at `data/chroma` (gitignored), one collection per repo |
| Orchestrate | `RepoIndexer` (`indexer.py`) | Runs fetch → chunk → embed → store, reports each `IndexingStage` via `on_stage` |
| Job | `run_indexing_job` (`indexing_jobs.py`) | `POST /index/repo` → 202 + `BackgroundTasks`; `GET /index/status/{repo_id}` |
| Retrieve | `CodeReviewer.review_pr_with_context` (`reviewer.py`) | Embeds the diff, takes the top 5 chunks, prepends them to the review message |

## Rules
1. **`Chunk` is the only unit passed between stages.** Extend or wrap it — never introduce a parallel "snippet"/"fragment" type
2. **Caller contract violations raise `ValueError`, not `AppError`** — e.g. an unsupported language in `CodeChunker`, or mismatched `chunks`/`embeddings` lengths in `VectorStore.add_chunks`
3. **Never accept `repo_id` from the client.** Derive it server-side as `{owner}__{repo}` lowercased (`REPO_ID_SEPARATOR`) from the parsed URL — and for `/review/pr`, only after `fetch_pr_diff` succeeds with the caller's token. Otherwise anyone could pull another repo's chunks into their review. The repo ID is both the job key and the Chroma collection name
4. **Run a single worker.** Jobs live in memory (`app.state.indexing_jobs`) — lost on restart and not shared between processes. One job per repo: re-indexing while `pending`/`running` returns 409; a `completed`/`failed` job is replaced. The GitHub token is never stored on the job
5. **Fetch and index agree on "supported" via `EXTENSION_TO_LANGUAGE`.** `RepoIndexer` doesn't trust `GitHubService`'s filter: unknown extensions are skipped (fail soft, no `KeyError`), as are files over `MAX_INDEXABLE_FILE_LINES`
6. **Re-indexing is idempotent.** Vector IDs are `{file_path}:{start_line}:{end_line}`, so upserts overwrite; call `delete_collection()` before a full re-index
7. **Sync Chroma calls never block the event loop** — they run via `asyncio.to_thread`
8. **Context is optional.** `review_pr_with_context` falls back to `review_pr_diff` when the collection is empty or search returns no chunks. Dependencies (`embedder`, `vector_store_factory`, Voyage `client`) are constructor-injected so tests use fakes
