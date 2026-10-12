"""Turn the `submit_code_review` tool's raw input into a `StructuredReview`.

The input is the model's JSON, so its `ReviewToolOutput` shape isn't
guaranteed: every way it can be wrong becomes `MalformedAIResponseError`,
never a raw `KeyError`, `TypeError` or `ValidationError`.
"""

from typing import cast

from pydantic import ValidationError

from app.exceptions import MalformedAIResponseError
from app.models.review import Finding, FindingCategory, StructuredReview
from app.prompts.review import FindingToolOutput, ReviewToolOutput

# STRUCTURED_REVIEW_TOOL marks bugs/security_issues/suggestions/positives as
# required too, but Claude has been observed to omit them despite that, so
# they're deliberately excluded here and defaulted via `.get(..., [])` below
# instead of raising. TODO: decide whether to loosen the schema to match this
# (needs a live test against the real API to see if that changes compliance,
# rather than guessing).
_REQUIRED_REVIEW_FIELDS = ("summary", "severity", "score", "detected_language")
# Finding fields the server always sets itself; dropped from tool input even if
# Claude volunteers them, so they can never come from the model.
_SERVER_SET_FINDING_FIELDS = frozenset({"id", "category"})


def _require_review_fields(data: ReviewToolOutput) -> None:
    missing = [field for field in _REQUIRED_REVIEW_FIELDS if field not in data]
    if missing:
        raise MalformedAIResponseError(
            f"Tool response missing required fields: {', '.join(missing)}"
        )


def _to_finding(item: FindingToolOutput, category: FindingCategory) -> Finding:
    """Validate one raw tool finding, tagging it with its list's category."""
    # A plain string here would otherwise escape as a TypeError.
    if not isinstance(item, dict):
        raise MalformedAIResponseError(
            "Tool response finding is not an object", debug_context=repr(item)
        )
    model_fields = {
        key: value
        for key, value in item.items()
        if key not in _SERVER_SET_FINDING_FIELDS
    }
    return Finding.model_validate({**model_fields, "category": category})


def _to_findings(
    items: list[FindingToolOutput], category: FindingCategory
) -> list[Finding]:
    """Validate the tool's raw findings, tagging each with its list's category."""
    return [_to_finding(item, category) for item in items]


def _build_structured_review(data: ReviewToolOutput) -> StructuredReview:
    """Turn validated tool output into the domain review.

    Raises:
        MalformedAIResponseError: If any finding fails `Finding` validation.
    """
    try:
        return StructuredReview(
            detected_language=data["detected_language"],
            summary=data["summary"],
            severity=data["severity"],
            score=data["score"],
            bugs=_to_findings(data.get("bugs", []), FindingCategory.BUG),
            security_issues=_to_findings(
                data.get("security_issues", []), FindingCategory.SECURITY
            ),
            suggestions=_to_findings(
                data.get("suggestions", []), FindingCategory.SUGGESTION
            ),
            positives=_to_findings(data.get("positives", []), FindingCategory.POSITIVE),
        )
    except ValidationError as e:
        raise MalformedAIResponseError(
            "Tool response contains an invalid finding", debug_context=str(e)
        ) from e


class ReviewParser:
    """Validates `submit_code_review` tool input into a domain `StructuredReview`.

    The server stamps each finding's `category` from the list it came in, and
    `Finding` generates its `id`; neither is ever read from the tool input.
    """

    def parse(self, tool_input: object) -> StructuredReview:
        """Build the review from the tool call's raw input.

        Raises:
            MalformedAIResponseError: A required field is missing, or a finding
                is not an object or fails `Finding` validation.
        """
        data = cast(ReviewToolOutput, tool_input)
        _require_review_fields(data)
        return _build_structured_review(data)
