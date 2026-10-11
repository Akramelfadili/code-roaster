from enum import StrEnum
from typing import Literal, get_args

Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_VALUES: tuple[Severity, ...] = get_args(Severity)

ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 2048

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

# Shown to clients in place of an unmodeled exception's real message.
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
