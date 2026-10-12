from enum import StrEnum
from typing import Literal, get_args

Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_VALUES: tuple[Severity, ...] = get_args(Severity)

ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 2048

# USD per million tokens for ANTHROPIC_MODEL (claude-sonnet-4-6), used to log
# an approximate cost per Claude call. Update together with ANTHROPIC_MODEL.
ANTHROPIC_INPUT_COST_PER_MTOK_USD = 3.00
ANTHROPIC_OUTPUT_COST_PER_MTOK_USD = 15.00
ANTHROPIC_CACHE_WRITE_COST_PER_MTOK_USD = 3.75
ANTHROPIC_CACHE_READ_COST_PER_MTOK_USD = 0.30
TOKENS_PER_MTOK = 1_000_000

# Input caps. Every LLM and embedding call is bounded by one of these, so no
# single request can fill Claude's context window or run up an unbounded bill.
# Request fields over their cap are rejected with a 422; content the server
# fetches or builds itself (diffs, retrieved context, queries) is truncated.
MAX_CODE_CHARS = 50_000
MAX_LANGUAGE_CHARS = 500
MAX_PR_URL_CHARS = 500
MAX_DIFF_CHARS = 100_000
MAX_CONTEXT_CHARS = 20_000
MAX_QUERY_CHARS = 10_000

# Maps each indexable source file extension to the canonical language name
# CodeChunker expects. Shared by GitHubService (which files to fetch from a
# repo) and RepoIndexer (which language to chunk a fetched file as).
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}
SUPPORTED_CODE_EXTENSIONS: frozenset[str] = frozenset(EXTENSION_TO_LANGUAGE)

# Files longer than this are skipped during indexing — too large to be a
# useful, focused chunk of retrieval context.
MAX_INDEXABLE_FILE_LINES = 500

# Joins a repository's owner and name into the ID that keys its indexing job
# and names its vector store collection, e.g. `octocat__hello-world`.
REPO_ID_SEPARATOR = "__"

INTERNAL_SERVER_ERROR_MESSAGE = "Internal server error"


class IndexingStage(StrEnum):
    """The RepoIndexer pipeline step currently running."""

    FETCHING = "fetching"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"


class IndexingJobState(StrEnum):
    """Lifecycle state of a background repository indexing job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# An indexing job still pending or running at startup whose row hasn't been
# updated for this long is assumed orphaned by a restart and marked failed.
# Kept well above the longest gap between stage updates, so a job still
# running on another worker isn't swept.
INDEXING_JOB_TIMEOUT_SECONDS = 30 * 60
INDEXING_JOB_ORPHANED_ERROR = "Server restarted"


class ReviewStage(StrEnum):
    """The `CodeReviewer` PR review step currently running."""

    RETRIEVING = "retrieving"
    REVIEWING = "reviewing"


class ReviewJobState(StrEnum):
    """Lifecycle state of a background PR review job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewEventType(StrEnum):
    """Type of one event in a review job's SSE stream.

    `completed` and `failed` are terminal: each job emits exactly one of them,
    last. V5 agent steps add new members here — stored as plain strings, so
    a new type needs no migration.
    """

    RETRIEVING = "retrieving"
    REVIEWING = "reviewing"
    FINDING = "finding"
    COMPLETED = "completed"
    FAILED = "failed"


# Same sweep as indexing jobs: a review job still pending or running at
# startup whose row hasn't been updated for this long is marked failed.
REVIEW_JOB_TIMEOUT_SECONDS = 30 * 60
REVIEW_JOB_ORPHANED_ERROR = "Server restarted"
