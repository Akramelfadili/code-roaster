from unittest.mock import AsyncMock, MagicMock

import pytest

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
    indexer = RepoIndexer(mock_github, mock_chunker, mock_embedder, mock_vector_store)
    return indexer, mock_github, mock_chunker, mock_embedder, mock_vector_store


class TestIndexRepository:
    async def test_returns_correct_indexing_result(self) -> None:
        indexer, _, mock_chunker, mock_embedder, mock_vector_store = _make_indexer(
            [("a.py", "def foo():\n    return 1\n")]
        )

        result = await indexer.index_repository("https://github.com/o/r", "token")

        assert result.repo_url == "https://github.com/o/r"
        assert result.files_processed == 1
        assert result.chunks_created == 1
        assert result.chunks_stored == 1
        assert result.duration_seconds >= 0
        mock_chunker.chunk_file.assert_called_once_with(
            "a.py", "def foo():\n    return 1\n", "python"
        )
        mock_embedder.embed_chunks.assert_called_once_with([_SAMPLE_CHUNK])
        mock_vector_store.add_chunks.assert_called_once_with(
            [_SAMPLE_CHUNK], [[0.1, 0.2]]
        )

    async def test_files_over_500_lines_are_skipped(self) -> None:
        big_content = "\n".join(f"x = {i}" for i in range(501))
        small_content = "def foo():\n    return 1\n"
        indexer, _, mock_chunker, _, _ = _make_indexer(
            [("big.py", big_content), ("small.py", small_content)]
        )

        result = await indexer.index_repository("https://github.com/o/r", "token")

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

        result = await indexer.index_repository("https://github.com/o/r", "token")

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
            await indexer.index_repository("https://github.com/o/missing", "token")
