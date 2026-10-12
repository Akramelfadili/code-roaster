---
paths:
  - 'app/services/chunker.py'
  - 'app/services/embedder.py'
  - 'app/services/vector_store.py'
  - 'app/services/indexer.py'
  - 'app/routes/index.py'
  - 'app/routes/pr.py'
---

# Editing the RAG pipeline

The full rules live in `app/claude-docs/rag-pipeline.md`. Before changing these files, check:
- Does the change still pass `Chunk` between stages, with no new parallel type?
- Is `repo_id` still derived server-side, never read from the request?
- Do `GitHubService` and `RepoIndexer` still agree on supported extensions via `EXTENSION_TO_LANGUAGE`?
- Are Chroma calls still wrapped in `asyncio.to_thread`?
- Does `app/claude-docs/rag-pipeline.md` (and `ARCHITECTURE.md` §5) need updating?
