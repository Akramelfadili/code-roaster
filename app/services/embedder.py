"""Embed code chunks into vectors for the RAG pipeline.

`Embedder` wraps Voyage AI's embeddings API. It turns `Chunk`s produced by the
chunker into dense document vectors for storage, and turns a natural-language
search string into a query vector in the same space for retrieval. It is the
embed stage of the pipeline (chunk -> embed -> store -> retrieve).
"""

import logging
from typing import cast

from voyageai.client_async import AsyncClient
from voyageai.error import RateLimitError, VoyageError

from app.config import settings
from app.exceptions import AIProviderError, AIProviderRateLimitError
from app.services.chunker import Chunk

logger = logging.getLogger(__name__)


_EMBEDDING_MODEL = "voyage-code-3"
_MAX_BATCH_SIZE = 128
# `input_type` tags each text's role so documents and the queries that search
# them are embedded into a compatible space; the two must not be mixed up.
_DOCUMENT_INPUT_TYPE = "document"
_QUERY_INPUT_TYPE = "query"


class Embedder:
    """Converts text into Voyage AI embedding vectors for the RAG pipeline."""

    def __init__(self, client: AsyncClient | None = None) -> None:
        """Create an embedder.

        Args:
            client: Voyage AI async client to use. Defaults to a fresh client
                authenticated with ``settings.voyage_api_key``; pass a fake in
                tests to avoid hitting the API.
        """
        self._client = client or AsyncClient(api_key=settings.voyage_api_key)
        self._model = _EMBEDDING_MODEL

    async def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Embed code chunks as document vectors, one per chunk.

        Chunks are sent to Voyage AI in batches of at most ``_MAX_BATCH_SIZE``
        to stay within the API's per-request input limit. Only each chunk's
        ``content`` is sent; the returned vectors are in the same order as
        ``chunks``.

        Args:
            chunks: Chunks to embed.

        Returns:
            One embedding vector per input chunk, in input order. Empty when
            ``chunks`` is empty (no API call is made).

        Raises:
            AIProviderRateLimitError: If Voyage AI rejects a request for
                exceeding its rate limit.
            AIProviderError: If any other Voyage AI API call fails.
        """
        vectors: list[list[float]] = []
        for batch_start in range(0, len(chunks), _MAX_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + _MAX_BATCH_SIZE]
            texts = [chunk.content for chunk in batch]
            vectors.extend(await self._embed(texts, _DOCUMENT_INPUT_TYPE))
        return vectors

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single search string as a query vector for retrieval.

        The query is embedded with ``input_type='query'`` so it lands in the
        same space as the document vectors produced by ``embed_chunks``.

        Args:
            query: The natural-language search string.

        Returns:
            The query's embedding vector.

        Raises:
            AIProviderRateLimitError: If Voyage AI rejects the request for
                exceeding its rate limit.
            AIProviderError: If the Voyage AI API call fails for any other
                reason.
        """
        vectors = await self._embed([query], _QUERY_INPUT_TYPE)
        return vectors[0]

    async def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        """Embed one batch of texts, translating Voyage AI failures to domain errors.

        Args:
            texts: The batch to embed; must not exceed ``_MAX_BATCH_SIZE``.
            input_type: Either ``_DOCUMENT_INPUT_TYPE`` or ``_QUERY_INPUT_TYPE``.

        Returns:
            One embedding vector per input text, in input order.

        Raises:
            AIProviderRateLimitError: On a Voyage AI rate-limit response.
            AIProviderError: On any other Voyage AI failure.
        """
        try:
            response = await self._client.embed(
                texts, model=self._model, input_type=input_type
            )
        except RateLimitError as e:
            raise AIProviderRateLimitError("Voyage AI rate limit exceeded") from e
        except VoyageError as e:
            raise AIProviderError("Voyage AI embedding request failed") from e

        logger.info(
            f"Token usage — type=embedding input_type={input_type} "
            f"texts={len(texts)} input={response.total_tokens}"
        )
        return cast(list[list[float]], response.embeddings)
