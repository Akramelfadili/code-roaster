import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from chromadb.api.models.Collection import Collection
from chromadb.errors import InternalError

from app.exceptions import VectorStoreError
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
    async def test_add_chunks_stores_correctly_and_search_returns_most_similar(
        self, tmp_path: Path
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))
        chunk_a = _make_chunk("a.py", "content a")
        chunk_b = _make_chunk("b.py", "content b")
        chunk_c = _make_chunk("c.py", "content c")
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

        await store.add_chunks([chunk_a, chunk_b, chunk_c], embeddings)
        results = await store.search([0.9, 0.1, 0.0], n_results=2)

        assert len(results) == 2
        assert results[0].file_path == "a.py"
        assert results[0].content == "content a"

    async def test_mismatched_lengths_raise_value_error(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        with pytest.raises(ValueError, match="same length"):
            await store.add_chunks(
                [_make_chunk("a.py"), _make_chunk("b.py")], [[1.0, 0.0, 0.0]]
            )

    async def test_empty_chunks_is_a_no_op(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        await store.add_chunks([], [])

        assert await store.collection_exists() is False

    async def test_upsert_runs_off_the_event_loop_thread(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))
        upsert_thread_ids: list[int] = []

        def record_thread(*args: object, **kwargs: object) -> None:
            upsert_thread_ids.append(threading.get_ident())

        with patch.object(Collection, "upsert", side_effect=record_thread):
            await store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])

        assert upsert_thread_ids
        assert threading.get_ident() not in upsert_thread_ids


class TestBatching:
    async def test_chunks_over_max_batch_size_are_split_and_all_stored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))
        monkeypatch.setattr(store._client, "get_max_batch_size", lambda: 2)
        chunks = [_make_chunk(f"file_{index}.py") for index in range(5)]
        embeddings = [[1.0, 0.0, 0.0]] * len(chunks)

        with patch.object(
            Collection, "upsert", autospec=True, side_effect=Collection.upsert
        ) as upsert_spy:
            await store.add_chunks(chunks, embeddings)

        batch_sizes = [len(call.kwargs["ids"]) for call in upsert_spy.call_args_list]
        assert batch_sizes == [2, 2, 1]
        results = await store.search([1.0, 0.0, 0.0], n_results=10)
        assert {chunk.file_path for chunk in results} == {
            chunk.file_path for chunk in chunks
        }


class TestUpsert:
    async def test_upsert_overwrites_duplicates(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))
        chunk_v1 = _make_chunk("dup.py", "old content")
        chunk_v2 = _make_chunk("dup.py", "new content")

        await store.add_chunks([chunk_v1], [[1.0, 0.0, 0.0]])
        await store.add_chunks([chunk_v2], [[1.0, 0.0, 0.0]])
        results = await store.search([1.0, 0.0, 0.0], n_results=10)

        assert len(results) == 1
        assert results[0].content == "new content"


class TestCollectionExists:
    async def test_returns_false_before_any_chunks_added(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        assert await store.collection_exists() is False

    async def test_returns_true_after_chunks_added(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        await store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])

        assert await store.collection_exists() is True


class TestDeleteCollection:
    async def test_is_idempotent(self, tmp_path: Path) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        await store.delete_collection()
        await store.delete_collection()

        await store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])
        await store.delete_collection()

        assert await store.collection_exists() is False
        await store.delete_collection()


class TestErrorTranslation:
    async def test_chroma_error_on_add_raises_vector_store_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        def fail(*args: object, **kwargs: object) -> None:
            raise InternalError("disk full")

        monkeypatch.setattr(store._client, "get_or_create_collection", fail)

        with pytest.raises(VectorStoreError) as exc_info:
            await store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])

        assert exc_info.value.debug_context == "disk full"
        assert exc_info.value.client_message == "Vector store unavailable"
        assert isinstance(exc_info.value.__cause__, InternalError)

    async def test_chroma_value_error_on_upsert_raises_vector_store_error(
        self, tmp_path: Path
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        with (
            patch.object(
                Collection, "upsert", side_effect=ValueError("Batch size exceeds")
            ),
            pytest.raises(VectorStoreError),
        ):
            await store.add_chunks([_make_chunk("a.py")], [[1.0, 0.0, 0.0]])

    async def test_chroma_error_on_search_raises_vector_store_error(
        self, tmp_path: Path
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        with (
            patch.object(Collection, "query", side_effect=InternalError("boom")),
            pytest.raises(VectorStoreError),
        ):
            await store.search([1.0, 0.0, 0.0])

    async def test_chroma_error_on_collection_exists_raises_vector_store_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = VectorStore("test-repo", str(tmp_path))

        def fail(*args: object, **kwargs: object) -> None:
            raise InternalError("boom")

        monkeypatch.setattr(store._client, "get_collection", fail)

        with pytest.raises(VectorStoreError):
            await store.collection_exists()
