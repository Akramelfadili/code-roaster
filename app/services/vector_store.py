"""Store and search code chunk embeddings for the RAG pipeline.

`VectorStore` wraps a persistent Chroma collection. It is the store/retrieve
stage of the pipeline (chunk -> embed -> store -> retrieve): chunks and the
vectors `Embedder` produces for them go in, and the chunks nearest a query
vector come back out, reconstructed from their stored content and metadata.
"""

from collections.abc import Sequence
from typing import cast

import chromadb
from chromadb.api.types import Metadata

from app.services.chunker import Chunk

_DEFAULT_PERSIST_DIRECTORY = "data/chroma"


class VectorStore:
    """Persists and searches `Chunk` embeddings in a local Chroma collection."""

    def __init__(
        self,
        collection_name: str,
        persist_directory: str = _DEFAULT_PERSIST_DIRECTORY,
    ) -> None:
        """Create a vector store backed by a persistent Chroma collection.

        Args:
            collection_name: Name of the Chroma collection. Callers scope this
                to one repository so different repos' chunks never mix.
            persist_directory: Directory Chroma persists its data under,
                relative to the project root. Defaults to `data/chroma`.
        """
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=persist_directory)

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Store chunks with their embedding vectors.

        Each chunk's document ID is `{file_path}:{start_line}:{end_line}`, so
        re-adding a chunk for the same file range upserts the existing record
        instead of creating a duplicate.

        Args:
            chunks: Chunks to store.
            embeddings: One embedding vector per chunk, in the same order as
                `chunks`.

        Raises:
            ValueError: If `chunks` and `embeddings` have different lengths.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks and embeddings must be the same length, "
                f"got {len(chunks)} and {len(embeddings)}"
            )
        if not chunks:
            return
        collection = self._client.get_or_create_collection(self._collection_name)
        collection.upsert(
            ids=[self._chunk_id(chunk) for chunk in chunks],
            embeddings=cast(list[Sequence[float] | Sequence[int]], embeddings),
            documents=[chunk.content for chunk in chunks],
            metadatas=[self._chunk_metadata(chunk) for chunk in chunks],
        )

    def search(self, query_embedding: list[float], n_results: int = 5) -> list[Chunk]:
        """Find the chunks most similar to a query vector.

        Args:
            query_embedding: Vector to search against, in the same embedding
                space as the vectors passed to `add_chunks`.
            n_results: Maximum number of chunks to return.

        Returns:
            The most similar chunks, most similar first. Empty if the
            collection has no documents.
        """
        collection = self._client.get_or_create_collection(self._collection_name)
        results = collection.query(
            query_embeddings=cast(
                list[Sequence[float] | Sequence[int]], [query_embedding]
            ),
            n_results=n_results,
            include=["documents", "metadatas"],
        )
        documents = results["documents"]
        metadatas = results["metadatas"]
        if not documents or not metadatas:
            return []
        return [
            self._to_chunk(document, metadata)
            for document, metadata in zip(documents[0], metadatas[0], strict=True)
        ]

    def delete_collection(self) -> None:
        """Delete all stored vectors for this collection, e.g. before re-indexing.

        A no-op if the collection does not exist yet.
        """
        try:
            self._client.delete_collection(self._collection_name)
        except chromadb.errors.NotFoundError:
            pass

    def collection_exists(self) -> bool:
        """Check whether this collection exists and holds at least one document."""
        try:
            collection = self._client.get_collection(self._collection_name)
        except chromadb.errors.NotFoundError:
            return False
        return collection.count() > 0

    @staticmethod
    def _chunk_id(chunk: Chunk) -> str:
        """Build a chunk's deterministic document ID."""
        return f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"

    @staticmethod
    def _chunk_metadata(chunk: Chunk) -> Metadata:
        """Build the metadata stored alongside a chunk's vector."""
        return {
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
        }

    @staticmethod
    def _to_chunk(content: str, metadata: Metadata) -> Chunk:
        """Reconstruct a `Chunk` from its stored document text and metadata."""
        return Chunk(
            content=content,
            file_path=str(metadata["file_path"]),
            start_line=cast(int, metadata["start_line"]),
            end_line=cast(int, metadata["end_line"]),
            language=str(metadata["language"]),
        )
