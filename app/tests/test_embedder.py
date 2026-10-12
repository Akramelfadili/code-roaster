import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voyageai.error

from app.constants import MAX_QUERY_CHARS
from app.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    BudgetExceededError,
)
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


class TestEmbedQuery:
    async def test_query_over_max_length_is_truncated_before_embedding(
        self,
    ) -> None:
        query = "q" * (MAX_QUERY_CHARS + 1)
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_fake_embed)
        embedder = Embedder(client=mock_client)

        await embedder.embed_query(query)

        mock_client.embed.assert_called_once_with(
            [query[:MAX_QUERY_CHARS]], model="voyage-code-3", input_type="query"
        )


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


class TestCostBudgetEnforcement:
    async def test_each_batch_checks_budget_and_records_its_cost(
        self, mock_cost_budget: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_fake_embed)
        embedder = Embedder(client=mock_client, budget=mock_cost_budget)

        await embedder.embed_chunks(_make_chunks(_MAX_BATCH_SIZE + 1))

        assert mock_cost_budget.ensure_available.await_count == 2
        recorded_costs = [
            call.args[0] for call in mock_cost_budget.record.await_args_list
        ]
        assert recorded_costs == pytest.approx(
            [_MAX_BATCH_SIZE * 0.18 / 1_000_000, 1 * 0.18 / 1_000_000]
        )

    async def test_exceeded_budget_blocks_embedding_call(
        self, mock_cost_budget: MagicMock
    ) -> None:
        mock_cost_budget.ensure_available.side_effect = BudgetExceededError("spent")
        mock_client = MagicMock()
        mock_client.embed = AsyncMock(side_effect=_fake_embed)
        embedder = Embedder(client=mock_client, budget=mock_cost_budget)

        with pytest.raises(BudgetExceededError):
            await embedder.embed_query("find the parser")
        mock_client.embed.assert_not_called()
