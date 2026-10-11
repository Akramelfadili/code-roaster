from app.models.pr import PullRequestRef
from app.models.review import Confidence, Finding, FindingCategory, StructuredReview
from app.services.chunker import Chunk
from app.services.indexer import IndexingResult

SAMPLE_CODE = "def add(a: int, b: int) -> int:\n    return a + b"

SAMPLE_PR_URL = "https://github.com/octocat/hello-world/pull/42"
SAMPLE_PR_REF = PullRequestRef(owner="octocat", repo="hello-world", number=42)
SAMPLE_PR_DIFF = "diff --git a/main.py b/main.py\n+print('hello')"

SAMPLE_STRUCTURED_REVIEW = StructuredReview(
    detected_language="Python",
    summary="Clean, readable function with no major issues.",
    severity="low",
    score=8,
    bugs=[],
    security_issues=[],
    suggestions=[
        Finding(
            category=FindingCategory.SUGGESTION,
            severity="low",
            file="main.py",
            line_start=1,
            line_end=2,
            title="Missing docstring",
            explanation="The function's purpose isn't documented.",
            suggestion="Add a one-line docstring.",
            confidence=Confidence.HIGH,
        )
    ],
    positives=[
        Finding(
            category=FindingCategory.POSITIVE,
            title="Good use of type hints",
            explanation="Parameters and return value are fully annotated.",
            confidence=Confidence.HIGH,
        )
    ],
)

SAMPLE_REPO_URL = "https://github.com/Octocat/Hello-World"
SAMPLE_REPO_REF = ("Octocat", "Hello-World")
SAMPLE_REPO_ID = "octocat__hello-world"
SAMPLE_INDEXING_RESULT = IndexingResult(
    repo_url=SAMPLE_REPO_URL,
    files_processed=3,
    chunks_created=7,
    chunks_stored=7,
    duration_seconds=1.5,
)

SAMPLE_CHUNK = Chunk(
    content="def helper() -> int:\n    return 1",
    file_path="app/helpers.py",
    start_line=10,
    end_line=11,
    language="python",
)
