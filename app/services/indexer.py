"""Orchestrate the RAG indexing pipeline for a repository.

`RepoIndexer` runs the full pipeline (fetch -> chunk -> embed -> store): it
pulls a repository's supported source files via `GitHubService`, splits them
into `Chunk`s with `CodeChunker`, embeds them with `Embedder`, and persists
the result in `VectorStore`.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.constants import (
    EXTENSION_TO_LANGUAGE,
    MAX_INDEXABLE_FILE_LINES,
    IndexingStage,
)
from app.services.chunker import Chunk, CodeChunker
from app.services.embedder import Embedder
from app.services.github import GitHubService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


async def _ignore_stage(_stage: IndexingStage) -> None:
    """Default `on_stage`: progress reporting is optional."""


@dataclass(frozen=True, slots=True)
class IndexingResult:
    """Summary of one `RepoIndexer.index_repository` run.

    Attributes:
        repo_url: URL of the repository that was indexed.
        files_processed: Number of supported files fetched from GitHub.
        chunks_created: Total chunks produced across all processed files.
        chunks_stored: Chunks upserted into the vector store.
        duration_seconds: Wall-clock time the pipeline took, end to end.
    """

    repo_url: str
    files_processed: int
    chunks_created: int
    chunks_stored: int
    duration_seconds: float


class RepoIndexer:
    """Runs the fetch -> chunk -> embed -> store pipeline for one repository."""

    def __init__(
        self,
        github_service: GitHubService,
        chunker: CodeChunker,
        embedder: Embedder,
        vector_store_factory: Callable[[str], VectorStore],
    ) -> None:
        """Wire the indexer to its pipeline collaborators.

        Args:
            github_service: Fetches a repository's supported source files.
            chunker: Splits each file's content into `Chunk`s.
            embedder: Turns chunks into embedding vectors.
            vector_store_factory: Builds the `VectorStore` for a collection
                name, so one indexer can serve many repositories, each in
                its own collection.
        """
        self._github_service = github_service
        self._chunker = chunker
        self._embedder = embedder
        self._vector_store_factory = vector_store_factory

    async def index_repository(
        self,
        repo_url: str,
        github_token: str,
        collection_name: str,
        on_stage: Callable[[IndexingStage], Awaitable[None]] | None = None,
    ) -> IndexingResult:
        """Fetch, chunk, embed, and store a repository's supported source files.

        The collection is cleared before storing, so chunks from files deleted
        or renamed since a previous run don't linger in the index.

        Args:
            repo_url: HTTPS URL of the repository to index.
            github_token: GitHub access token used to fetch its files.
            collection_name: Vector store collection to store the chunks in.
            on_stage: Awaited as each pipeline stage starts, to report progress
                (the job runner persists it, so it is async).

        Returns:
            Summary counts and timing for the run.
        """
        report_stage = on_stage or _ignore_stage
        start_time = time.monotonic()
        logger.info(f"Starting indexing for {repo_url}")

        await report_stage(IndexingStage.FETCHING)
        files = await self._github_service.fetch_repo_files(repo_url, github_token)
        logger.info(f"Fetched {len(files)} source files from {repo_url}")

        await report_stage(IndexingStage.CHUNKING)
        chunks = await asyncio.to_thread(self._chunk_files, files)
        logger.info(f"Created {len(chunks)} chunks from {len(files)} files")

        await report_stage(IndexingStage.EMBEDDING)
        embeddings = await self._embedder.embed_chunks(chunks)
        logger.info(f"Embedded {len(embeddings)} chunks")

        await report_stage(IndexingStage.STORING)
        vector_store = self._vector_store_factory(collection_name)
        await vector_store.delete_collection()
        await vector_store.add_chunks(chunks, embeddings)
        logger.info(f"Stored {len(chunks)} chunks for {repo_url}")

        return IndexingResult(
            repo_url=repo_url,
            files_processed=len(files),
            chunks_created=len(chunks),
            chunks_stored=len(chunks),
            duration_seconds=time.monotonic() - start_time,
        )

    def _chunk_files(self, files: list[tuple[str, str]]) -> list[Chunk]:
        """Chunk each file, skipping oversized or unsupported-extension ones."""
        chunks: list[Chunk] = []
        for file_path, content in files:
            if len(content.splitlines()) > MAX_INDEXABLE_FILE_LINES:
                logger.info(
                    f"Skipping {file_path}: exceeds {MAX_INDEXABLE_FILE_LINES} lines"
                )
                continue
            language = EXTENSION_TO_LANGUAGE.get(PurePosixPath(file_path).suffix)
            if language is None:
                logger.info(f"Skipping {file_path}: unsupported extension")
                continue
            chunks.extend(self._chunker.chunk_file(file_path, content, language))
        return chunks
