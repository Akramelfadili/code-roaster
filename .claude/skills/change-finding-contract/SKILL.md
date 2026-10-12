---
name: change-finding-contract
description: Add, remove or change a field on the review Finding (or StructuredReviewResponse). Use whenever a task touches Finding, _FINDING_SCHEMA, FindingToolOutput, FindingSchema or mapToFinding — the contract spans backend, prompt, frontend and docs.
---

# Changing the Finding contract

The contract is the `Finding` model in `app/models/review.py`; its rationale is in ARCHITECTURE.md §3.7. Touch every step in order and skip none.

## Backend
1. `app/models/review.py` → `Finding`. A new field is optional (`X | None = None`) unless the review is useless without it: a required field Claude omits fails the whole review.
2. `app/prompts/review.py` → `_FINDING_SCHEMA` (JSON schema) and `FindingToolOutput` (its TypedDict mirror), changed together. Update the system prompt text if Claude needs instructions to fill the field.
3. `id` and `category` are server-set. Never add them to the schema or TypedDict, and never read them from tool input.
4. `app/services/review_parser.py` changes only if the field needs server-side handling. Findings are still built via `Finding.model_validate`, and failures become `MalformedAIResponseError`.
5. Tests: `app/tests/test_reviewer.py` (field present, absent, invalid → `MalformedAIResponseError`) and shared data in `app/tests/mocks.py`.
5a. If stored results in the old shape would no longer validate (a new required field, a removed or retyped one), bump `REVIEW_RESULT_SCHEMA_VERSION` in `app/constants.py`. Review jobs saved in the old shape then read as failed with "result schema outdated" instead of raising.

## Frontend
6. `frontend/src/types/review.ts` → `FindingSchema` (use `.nullable()`, not `.optional()`: absent fields arrive as `null`) and the camelCase `Finding` domain type.
7. `frontend/src/api/review.ts` → `mapToFinding`.
8. `frontend/src/components/Section.tsx` if the field is user-visible.
9. Tests: `src/tests/api/review.test.ts`, `src/tests/components/ReviewResult.test.tsx`.

## Docs
10. The *Review Findings* table in `app/CLAUDE.md`, and the field list in `frontend/claude-docs/data-layer.md`.

## Verify
`make check-all`. Report any skipped tests explicitly.
