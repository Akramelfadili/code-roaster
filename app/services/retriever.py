"""Retrieve indexed code chunks relevant to a query for the RAG pipeline.

`CodeRetriever` is the retrieve stage of the pipeline (chunk -> embed -> store
-> retrieve): it embeds a query with `Embedder` and searches the repository's
`VectorStore` collection for the nearest chunks. It is a standalone service so
any caller — the reviewer today, agent tools later — can retrieve context
without owning the embedding or vector store plumbing.
"""

import logging
from collections.abc import Callable

from app.exceptions import AIProviderError
from app.services.chunker import Chunk
from app.services.embedder import Embedder
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

_DEFAULT_RETRIEVED_CHUNK_COUNT = 5


class CodeRetriever:
    """Finds the indexed chunks of a repository most relevant to a query."""

    def __init__(
        self,
        embedder: Embedder,
        vector_store_factory: Callable[[str], VectorStore],
    ) -> None:
        """Wire the retriever to its pipeline collaborators.

        Args:
            embedder: Embeds the query into the same space as the indexed chunks.
            vector_store_factory: Builds the `VectorStore` for a collection
                name, so one retriever can serve many repositories.
        """
        self._embedder = embedder
        self._vector_store_factory = vector_store_factory

    async def retrieve(
        self, repo_id: str, query: str, k: int = _DEFAULT_RETRIEVED_CHUNK_COUNT
    ) -> list[Chunk]:
        """Return up to `k` indexed chunks of a repository nearest to `query`.

        `repo_id` must be derived server-side from a repository the caller can
        access, never taken from client input, or another repo's code leaks.

        Context is optional, so an embedding failure is logged and yields no
        chunks rather than failing the caller.

        Args:
            repo_id: The repository's collection name (`{owner}__{repo}`).
            query: Text to search with, e.g. a PR diff.
            k: Maximum number of chunks to return.

        Returns:
            The nearest chunks, most similar first. Empty if the repository
            has no index or the query could not be embedded.

        Raises:
            VectorStoreError: If Chroma fails to read or search the collection.
            BudgetExceededError: If the daily cost budget blocks the query
                embedding. Unlike other embedding failures it propagates, since
                the review call that follows would be blocked too.
        """
        vector_store = self._vector_store_factory(repo_id)
        if not await vector_store.collection_exists():
            return []

        try:
            query_vector = await self._embedder.embed_query(query)
        except AIProviderError as e:
            logger.warning(
                f"Retrieval skipped for {repo_id}: query embedding failed: {e}"
            )
            return []

        return await vector_store.search(query_vector, k)
