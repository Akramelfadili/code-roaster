import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voyageai.error

from app.exceptions import AIProviderError, AIProviderRateLimitError
from app.services.chunker import Chunk
from app.services.embedder import Embedder

_MAX_BATCH_SIZE = 128


def _make_chunks(count: int) -> list[Chunk]:
    return [
        Chunk(
            content=f"chunk {i}",
            file_path="sample.py",
            start_line=i,
            end_line=i,
            language="python",
        )
        for i in range(count)
    ]


async def _fake_embed(
    texts: list[str], *, model: str, input_type: str
) -> SimpleNamespace:
    return SimpleNamespace(
        embeddings=[[0.0, float(i)] for i in range(len(texts))],
        total_tokens=len(texts),
    )


def _rate_limit_error() -> voyageai.error.RateLimitError:
    return voyageai.error.RateLimitError("rate limited")  # type: ignore[no-untyped-call]


def _voyage_error() -> voyageai.error.VoyageError:
    return voyageai.error.VoyageError("boom")  # type: ignore[no-untyped-call]


class TestEmbedChunks:
    async def test_returns_one_vector_per_chunk(self) -> None:
        chunks = _make_chunks(3)
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_fake_embed)
        embedder = Embedder(client=mock_client)

        vectors = await embedder.embed_chunks(chunks)

        assert len(vectors) == 3
        mock_client.embed.assert_called_once_with(
            [c.content for c in chunks], model="voyage-code-3", input_type="document"
        )

    async def test_batches_correctly_at_128_inputs(self) -> None:
        chunks = _make_chunks(150)
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_fake_embed)
        embedder = Embedder(client=mock_client)

        vectors = await embedder.embed_chunks(chunks)

        assert len(vectors) == 150
        assert mock_client.embed.call_count == math.ceil(150 / _MAX_BATCH_SIZE)
        first_call_texts = mock_client.embed.call_args_list[0].args[0]
        second_call_texts = mock_client.embed.call_args_list[1].args[0]
        assert len(first_call_texts) == _MAX_BATCH_SIZE
        assert len(second_call_texts) == 150 - _MAX_BATCH_SIZE

    async def test_empty_list_returns_empty_list_no_api_call(self) -> None:
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_fake_embed)
        embedder = Embedder(client=mock_client)

        vectors = await embedder.embed_chunks([])

        assert vectors == []
        mock_client.embed.assert_not_called()

    async def test_rate_limit_error_raises_ai_provider_rate_limit_error(self) -> None:
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_rate_limit_error())
        embedder = Embedder(client=mock_client)

        with pytest.raises(AIProviderRateLimitError):
            await embedder.embed_chunks(_make_chunks(1))

    async def test_voyage_error_raises_ai_provider_error(self) -> None:
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_voyage_error())
        embedder = Embedder(client=mock_client)

        with pytest.raises(AIProviderError):
            await embedder.embed_chunks(_make_chunks(1))
