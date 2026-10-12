from app.constants import MAX_CONTEXT_CHARS
from app.services.chunker import Chunk
from app.services.context_builder import _fit_context_budget


class TestFitContextBudget:
    # Each chunk's formatted size is just over a third of the budget, so only
    # the first two fit.
    _CHUNK_CONTENT_CHARS = MAX_CONTEXT_CHARS // 3

    def _make_ranked_chunks(self, count: int) -> list[Chunk]:
        return [
            Chunk(
                content="x" * self._CHUNK_CONTENT_CHARS,
                file_path=f"rank_{rank}.py",
                start_line=1,
                end_line=2,
                language="python",
            )
            for rank in range(count)
        ]

    def test_over_budget_drops_lowest_ranked_chunks_first(self) -> None:
        chunks = self._make_ranked_chunks(4)

        assert _fit_context_budget(chunks) == chunks[:2]

    def test_within_budget_keeps_every_chunk(self) -> None:
        chunks = self._make_ranked_chunks(2)

        assert _fit_context_budget(chunks) == chunks
