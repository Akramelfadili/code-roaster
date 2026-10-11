from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    VectorStoreError,
)
from app.services.embedder import Embedder
from app.services.retriever import CodeRetriever
from app.services.vector_store import VectorStore
from app.tests.mocks import SAMPLE_CHUNK, SAMPLE_REPO_ID

_QUERY = "diff --git a/f b/f"
_QUERY_VECTOR = [0.1, 0.2]


def _make_retriever(
    collection_exists: bool = True,
) -> tuple[CodeRetriever, MagicMock, MagicMock, MagicMock]:
    vector_store = MagicMock(spec=VectorStore)
    vector_store.collection_exists = AsyncMock(return_value=collection_exists)
    vector_store.search = AsyncMock(return_value=[SAMPLE_CHUNK])
    vector_store_factory = MagicMock(return_value=vector_store)
    embedder = MagicMock(spec=Embedder)
    embedder.embed_query = AsyncMock(return_value=_QUERY_VECTOR)
    retriever = CodeRetriever(
        embedder=embedder, vector_store_factory=vector_store_factory
    )
    return retriever, embedder, vector_store_factory, vector_store


class TestRetrieve:
    async def test_indexed_repo_returns_nearest_chunks(self) -> None:
        retriever, embedder, vector_store_factory, vector_store = _make_retriever()

        chunks = await retriever.retrieve(SAMPLE_REPO_ID, _QUERY, k=3)

        assert chunks == [SAMPLE_CHUNK]
        vector_store_factory.assert_called_once_with(SAMPLE_REPO_ID)
        embedder.embed_query.assert_awaited_once_with(_QUERY)
        vector_store.search.assert_awaited_once_with(_QUERY_VECTOR, 3)

    async def test_default_k_searches_five_chunks(self) -> None:
        retriever, _, _, vector_store = _make_retriever()

        await retriever.retrieve(SAMPLE_REPO_ID, _QUERY)

        vector_store.search.assert_awaited_once_with(_QUERY_VECTOR, 5)

    async def test_missing_collection_returns_empty_without_embedding(self) -> None:
        retriever, embedder, _, vector_store = _make_retriever(collection_exists=False)

        chunks = await retriever.retrieve(SAMPLE_REPO_ID, _QUERY)

        assert chunks == []
        embedder.embed_query.assert_not_awaited()
        vector_store.search.assert_not_awaited()

    @pytest.mark.parametrize(
        "embedding_error",
        [
            AIProviderError("Voyage AI embedding request failed"),
            AIProviderRateLimitError("Voyage AI rate limit exceeded"),
        ],
    )
    async def test_embedding_failure_returns_empty(
        self, embedding_error: AIProviderError
    ) -> None:
        retriever, embedder, _, vector_store = _make_retriever()
        embedder.embed_query.side_effect = embedding_error

        chunks = await retriever.retrieve(SAMPLE_REPO_ID, _QUERY)

        assert chunks == []
        vector_store.search.assert_not_awaited()

    async def test_vector_store_failure_propagates(self) -> None:
        retriever, _, _, vector_store = _make_retriever()
        vector_store.search.side_effect = VectorStoreError("search failed")

        with pytest.raises(VectorStoreError):
            await retriever.retrieve(SAMPLE_REPO_ID, _QUERY)
