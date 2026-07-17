from app.reviewer import StructuredReview
from app.services.github import PullRequestRef

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
    suggestions=["Consider adding a docstring"],
    positives=["Good use of type hints", "Simple and correct logic"],
)
