from app.reviewer import StructuredReview

SAMPLE_CODE = "def add(a: int, b: int) -> int:\n    return a + b"

SAMPLE_STRUCTURED_REVIEW = StructuredReview(
    summary="Clean, readable function with no major issues.",
    severity="low",
    score=8,
    bugs=[],
    security_issues=[],
    suggestions=["Consider adding a docstring"],
    positives=["Good use of type hints", "Simple and correct logic"],
)
