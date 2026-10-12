import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants import IndexingStage
from app.exceptions import RepoNotFoundError
from app.services.chunker import Chunk, CodeChunker
from app.services.embedder import Embedder
from app.services.github import GitHubService
from app.services.indexer import RepoIndexer
from app.services.vector_store import VectorStore

_SAMPLE_CHUNK = Chunk(
    content="def foo():\n    return 1",
    file_path="a.py",
    start_line=1,
    end_line=2,
    language="python",
)


def _make_indexer(
    fetch_result: list[tuple[str, str]],
) -> tuple[RepoIndexer, MagicMock, MagicMock, MagicMock, MagicMock]:
    mock_github = MagicMock(spec=GitHubService)
    mock_github.fetch_repo_files = AsyncMock(return_value=fetch_result)
    mock_chunker = MagicMock(spec=CodeChunker)
    mock_chunker.chunk_file = MagicMock(return_value=[_SAMPLE_CHUNK])
    mock_embedder = MagicMock(spec=Embedder)
    mock_embedder.embed_chunks = AsyncMock(return_value=[[0.1, 0.2]])
    mock_vector_store = MagicMock(spec=VectorStore)
    mock_vector_store_factory = MagicMock(return_value=mock_vector_store)
    indexer = RepoIndexer(
        mock_github, mock_chunker, mock_embedder, mock_vector_store_factory
    )
    return indexer, mock_github, mock_chunker, mock_embedder, mock_vector_store


class TestIndexRepository:
    async def test_returns_correct_indexing_result(self) -> None:
        indexer, _, mock_chunker, mock_embedder, mock_vector_store = _make_indexer(
            [("a.py", "def foo():\n    return 1\n")]
        )

        result = await indexer.index_repository(
            "https://github.com/o/r", "token", "o__r"
        )

        assert result.repo_url == "https://github.com/o/r"
        assert result.files_processed == 1
        assert result.chunks_created == 1
        assert result.chunks_stored == 1
        assert result.duration_seconds >= 0
        mock_chunker.chunk_file.assert_called_once_with(
            "a.py", "def foo():\n    return 1\n", "python"
        )
        mock_embedder.embed_chunks.assert_called_once_with([_SAMPLE_CHUNK])
        mock_vector_store.add_chunks.assert_awaited_once_with(
            [_SAMPLE_CHUNK], [[0.1, 0.2]]
        )

    async def test_files_over_500_lines_are_skipped(self) -> None:
        big_content = "\n".join(f"x = {i}" for i in range(501))
        small_content = "def foo():\n    return 1\n"
        indexer, _, mock_chunker, _, _ = _make_indexer(
            [("big.py", big_content), ("small.py", small_content)]
        )

        result = await indexer.index_repository(
            "https://github.com/o/r", "token", "o__r"
        )

        assert result.files_processed == 2
        assert result.chunks_created == 1
        mock_chunker.chunk_file.assert_called_once_with(
            "small.py", small_content, "python"
        )

    async def test_unsupported_extensions_are_skipped(self) -> None:
        readme_content = "# Just a readme\nNothing to index here.\n"
        source_content = "def foo():\n    return 1\n"
        indexer, _, mock_chunker, _, _ = _make_indexer(
            [("README.md", readme_content), ("a.py", source_content)]
        )

        result = await indexer.index_repository(
            "https://github.com/o/r", "token", "o__r"
        )

        assert result.files_processed == 2
        assert result.chunks_created == 1
        mock_chunker.chunk_file.assert_called_once_with(
            "a.py", source_content, "python"
        )

    async def test_github_fetch_failure_raises_domain_exception(self) -> None:
        indexer, mock_github, _, _, _ = _make_indexer([])
        mock_github.fetch_repo_files = AsyncMock(
            side_effect=RepoNotFoundError("repo not found")
        )

        with pytest.raises(RepoNotFoundError):
            await indexer.index_repository(
                "https://github.com/o/missing", "token", "o__missing"
            )

    async def test_chunking_runs_off_the_event_loop_thread(self) -> None:
        indexer, _, mock_chunker, _, _ = _make_indexer(
            [("a.py", "def foo():\n    return 1\n")]
        )
        chunk_thread_ids: list[int] = []

        def record_thread(*args: object) -> list[Chunk]:
            chunk_thread_ids.append(threading.get_ident())
            return [_SAMPLE_CHUNK]

        mock_chunker.chunk_file.side_effect = record_thread

        await indexer.index_repository("https://github.com/o/r", "token", "o__r")

        assert chunk_thread_ids
        assert threading.get_ident() not in chunk_thread_ids

    async def test_reports_each_stage_in_order(self) -> None:
        indexer, _, _, _, _ = _make_indexer([("a.py", "def foo():\n    return 1\n")])
        reported_stages: list[IndexingStage] = []

        async def record_stage(stage: IndexingStage) -> None:
            reported_stages.append(stage)

        await indexer.index_repository(
            "https://github.com/o/r", "token", "o__r", on_stage=record_stage
        )

        assert reported_stages == [
            IndexingStage.FETCHING,
            IndexingStage.CHUNKING,
            IndexingStage.EMBEDDING,
            IndexingStage.STORING,
        ]

    async def test_reindexing_removes_stale_chunks(self, tmp_path: Path) -> None:
        source_content = "def foo():\n    return 1\n"
        mock_github = MagicMock(spec=GitHubService)
        mock_github.fetch_repo_files = AsyncMock(
            side_effect=[[("old.py", source_content)], [("new.py", source_content)]]
        )
        mock_chunker = MagicMock(spec=CodeChunker)
        mock_chunker.chunk_file = MagicMock(
            side_effect=lambda file_path, content, language: [
                Chunk(content, file_path, 1, 2, language)
            ]
        )
        mock_embedder = MagicMock(spec=Embedder)
        mock_embedder.embed_chunks = AsyncMock(
            side_effect=lambda chunks: [[1.0, 0.0]] * len(chunks)
        )
        vector_store = VectorStore("o__r", str(tmp_path))
        indexer = RepoIndexer(
            mock_github, mock_chunker, mock_embedder, lambda _name: vector_store
        )

        await indexer.index_repository("https://github.com/o/r", "token", "o__r")
        await indexer.index_repository("https://github.com/o/r", "token", "o__r")

        stored_file_paths = [
            chunk.file_path
            for chunk in await vector_store.search([1.0, 0.0], n_results=10)
        ]
        assert stored_file_paths == ["new.py"]
