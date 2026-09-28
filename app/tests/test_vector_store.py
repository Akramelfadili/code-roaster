from pathlib import Path

import pytest

from app.services.chunker import Chunk
from app.services.vector_store import VectorStore


def _make_chunk(file_path: str, content: str = "content") -> Chunk:
    return Chunk(
        content=content,
        file_path=file_path,
        start_line=1,
        end_line=5,
        language="python",
    )


class TestAddChunksAndSearch:
    def test_add_chunks_stores_correctly_and_search_returns_most_similar(
        self, tmp_path: Path
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))
        chunk_a = _make_chunk("a.py", "content a")
        chunk_b = _make_chunk("b.py", "content b")
        chunk_c = _make_chunk("c.py", "content c")
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

        store.add_chunks([chunk_a, chunk_b, chunk_c], embeddings)
        results = store.search([0.9, 0.1, 0.0], n_results=2)

        assert len(results) == 2
        assert results[0].file_path == "a.py"
        assert results[0].content == "content a"

    def test_mismatched_lengths_raise_value_error(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        with pytest.raises(ValueError, match="same length"):
            store.add_chunks(
                [_make_chunk("a.py"), _make_chunk("b.py")], [[1.0, 0.0, 0.0]]
            )

    def test_empty_chunks_is_a_no_op(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        store.add_chunks([], [])

        assert store.collection_exists() is False


class TestUpsert:
    def test_upsert_overwrites_duplicates(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))
        chunk_v1 = _make_chunk("dup.py", "old content")
        chunk_v2 = _make_chunk("dup.py", "new content")

        store.add_chunks([chunk_v1], [[1.0, 0.0, 0.0]])
        store.add_chunks([chunk_v2], [[1.0, 0.0, 0.0]])
        results = store.search([1.0, 0.0, 0.0], n_results=10)

        assert len(results) == 1
        assert results[0].content == "new content"


class TestCollectionExists:
    def test_returns_false_before_any_chunks_added(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        assert store.collection_exists() is False

    def test_returns_true_after_chunks_added(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])

        assert store.collection_exists() is True


class TestDeleteCollection:
    def test_is_idempotent(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        store.delete_collection()
        store.delete_collection()

        store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])
        store.delete_collection()

        assert store.collection_exists() is False
        store.delete_collection()
