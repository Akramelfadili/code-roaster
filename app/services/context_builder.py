"""Build the codebase context section of a PR review prompt.

`ContextBuilder` asks `CodeRetriever` for the indexed chunks nearest a query,
keeps the highest-ranked ones that fit `MAX_CONTEXT_CHARS`, and formats them
as labelled code blocks. It never touches `Embedder` or `VectorStore` itself:
retrieval stays in `CodeRetriever`.
"""

import logging

from app.constants import MAX_CONTEXT_CHARS
from app.services.chunker import Chunk
from app.services.retriever import CodeRetriever

logger = logging.getLogger(__name__)

_CONTEXT_CHUNK_SEPARATOR = "\n\n"


def _format_chunk(chunk: Chunk) -> str:
    return (
        f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
        f"```{chunk.language}\n{chunk.content}\n```"
    )


def _fit_context_budget(chunks: list[Chunk]) -> list[Chunk]:
    """Keep the highest-ranked chunks whose formatted context fits the budget.

    `chunks` arrive most relevant first, so the lowest-ranked ones are dropped
    first once the joined context would exceed `MAX_CONTEXT_CHARS`.
    """
    kept: list[Chunk] = []
    context_chars = 0
    for chunk in chunks:
        separator_chars = len(_CONTEXT_CHUNK_SEPARATOR) if kept else 0
        chunk_chars = len(_format_chunk(chunk)) + separator_chars
        if context_chars + chunk_chars > MAX_CONTEXT_CHARS:
            break
        kept.append(chunk)
        context_chars += chunk_chars
    if len(kept) < len(chunks):
        logger.warning(
            f"Dropped {len(chunks) - len(kept)} of {len(chunks)} retrieved chunks "
            f"to fit the {MAX_CONTEXT_CHARS}-char context budget"
        )
    return kept


class ContextBuilder:
    """Turns a query into a size-capped, formatted codebase context string."""

    def __init__(self, retriever: CodeRetriever) -> None:
        """Wire the builder to the retriever it gets chunks from."""
        self._retriever = retriever

    async def build(self, repo_id: str, query: str) -> str | None:
        """Return formatted context for `query` from `repo_id`'s index.

        `repo_id` must be derived server-side from a repository the caller can
        access, never taken from client input, or another repo's code leaks.

        Returns:
            The fitted chunks as labelled code blocks, most relevant first, or
            `None` when nothing was retrieved or not even the top chunk fits.

        Raises:
            VectorStoreError: If Chroma fails to read or search the collection.
            BudgetExceededError: If the daily cost budget blocks the query
                embedding.
        """
        chunks = _fit_context_budget(await self._retriever.retrieve(repo_id, query))
        if not chunks:
            return None
        return _CONTEXT_CHUNK_SEPARATOR.join(_format_chunk(chunk) for chunk in chunks)
