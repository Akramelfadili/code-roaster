import json
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.constants import ReviewEventType, ReviewStage
from app.exceptions import GitHubAuthError, InvalidPRUrlError, PRNotFoundError
from app.models.pr import PullRequestRef
from app.models.review import StructuredReview
from app.tests.mocks import (
    SAMPLE_PR_DIFF,
    SAMPLE_PR_URL,
    SAMPLE_REPO_ID,
    SAMPLE_STRUCTURED_REVIEW,
)

_PR_REVIEW_REQUEST = {"pr_url": SAMPLE_PR_URL, "github_token": "gh-token"}
_SSE_DATA_PREFIX = "data: "


def _parse_sse_data(body: str) -> list[dict[str, object]]:
    """Return the JSON payload of every `data:` line in an SSE body, in order."""
    return [
        json.loads(line.removeprefix(_SSE_DATA_PREFIX))
        for line in body.splitlines()
        if line.startswith(_SSE_DATA_PREFIX)
    ]


async def _review_reporting_stages(
    diff: str,
    repo_id: str,
    pr_label: str,
    on_stage: Callable[[ReviewStage], Awaitable[None]],
) -> StructuredReview:
    await on_stage(ReviewStage.RETRIEVING)
    await on_stage(ReviewStage.REVIEWING)
    return SAMPLE_STRUCTURED_REVIEW


async def _start_review_job(client: AsyncClient) -> str:
    response = await client.post("/review/pr/async", json=_PR_REVIEW_REQUEST)
    job_id: str = response.json()["job_id"]
    return job_id


class TestReviewPr:
    async def test_happy_path_returns_structured_review(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/review/pr",
            json={"pr_url": SAMPLE_PR_URL, "github_token": "gh-token"},
        )
        assert response.status_code == 200
        data = response.json()
        for field in (
            "detected_language",
            "summary",
            "severity",
            "score",
            "bugs",
            "security_issues",
            "suggestions",
            "positives",
        ):
            assert field in data

    async def test_reviews_with_context_using_repo_id_derived_from_pr_url(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        response = await client.post(
            "/review/pr",
            json={"pr_url": SAMPLE_PR_URL, "github_token": "gh-token"},
        )
        assert response.status_code == 200
        mock_reviewer.review_pr_with_context.assert_awaited_once_with(
            SAMPLE_PR_DIFF, SAMPLE_REPO_ID, "octocat/hello-world#42"
        )

    async def test_lowercases_derived_repo_id(
        self,
        client: AsyncClient,
        mock_github_service: MagicMock,
        mock_reviewer: MagicMock,
    ) -> None:
        mock_github_service.parse_pr_url.return_value = PullRequestRef(
            owner="Octocat", repo="Hello-World", number=42
        )
        response = await client.post(
            "/review/pr",
            json={"pr_url": SAMPLE_PR_URL, "github_token": "gh-token"},
        )
        assert response.status_code == 200
        _, repo_id, _ = mock_reviewer.review_pr_with_context.await_args.args
        assert repo_id == SAMPLE_REPO_ID

    async def test_client_supplied_repo_id_is_ignored(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        response = await client.post(
            "/review/pr",
            json={
                "pr_url": SAMPLE_PR_URL,
                "github_token": "gh-token",
                "repo_id": "victim__private-repo",
            },
        )
        assert response.status_code == 200
        _, repo_id, _ = mock_reviewer.review_pr_with_context.await_args.args
        assert repo_id == SAMPLE_REPO_ID

    async def test_inaccessible_pr_never_reaches_reviewer(
        self,
        client: AsyncClient,
        mock_github_service: MagicMock,
        mock_reviewer: MagicMock,
    ) -> None:
        mock_github_service.fetch_pr_diff.side_effect = PRNotFoundError("not found")
        response = await client.post(
            "/review/pr",
            json={"pr_url": SAMPLE_PR_URL, "github_token": "gh-token"},
        )
        assert response.status_code == 404
        mock_reviewer.review_pr_with_context.assert_not_awaited()

    async def test_empty_pr_url_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/review/pr", json={"pr_url": "   ", "github_token": "gh-token"}
        )
        assert response.status_code == 422

    async def test_invalid_pr_url_returns_400(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        mock_github_service.parse_pr_url.side_effect = InvalidPRUrlError("bad url")
        response = await client.post(
            "/review/pr",
            json={"pr_url": "https://example.com", "github_token": "gh-token"},
        )
        assert response.status_code == 400

    async def test_invalid_token_returns_401(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        mock_github_service.fetch_pr_diff.side_effect = GitHubAuthError("bad token")
        response = await client.post(
            "/review/pr",
            json={"pr_url": SAMPLE_PR_URL, "github_token": "bad-token"},
        )
        assert response.status_code == 401

    async def test_pr_not_found_returns_404(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        mock_github_service.fetch_pr_diff.side_effect = PRNotFoundError("not found")
        response = await client.post(
            "/review/pr",
            json={"pr_url": SAMPLE_PR_URL, "github_token": "gh-token"},
        )
        assert response.status_code == 404


@pytest.mark.usefixtures("db_session_factory")
class TestReviewPrAsync:
    async def test_happy_path_returns_202_with_job_id(
        self, client: AsyncClient
    ) -> None:
        response = await client.post("/review/pr/async", json=_PR_REVIEW_REQUEST)

        assert response.status_code == 202
        assert set(response.json()) == {"job_id"}

    async def test_runs_review_in_background_with_derived_repo_id(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        await client.post("/review/pr/async", json=_PR_REVIEW_REQUEST)

        args = mock_reviewer.review_pr_with_context.await_args.args
        assert args == (SAMPLE_PR_DIFF, SAMPLE_REPO_ID, "octocat/hello-world#42")

    async def test_invalid_pr_url_returns_400(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        mock_github_service.parse_pr_url.side_effect = InvalidPRUrlError("bad url")
        response = await client.post("/review/pr/async", json=_PR_REVIEW_REQUEST)
        assert response.status_code == 400

    async def test_empty_pr_url_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/review/pr/async", json={"pr_url": " ", "github_token": "gh-token"}
        )
        assert response.status_code == 422


@pytest.mark.usefixtures("db_session_factory")
class TestReviewPrEvents:
    async def test_completed_job_streams_stages_findings_then_completed(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        mock_reviewer.review_pr_with_context = AsyncMock(
            side_effect=_review_reporting_stages
        )
        job_id = await _start_review_job(client)

        response = await client.get(f"/review/pr/{job_id}/events")

        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_data(response.text)
        assert [event["type"] for event in events] == [
            ReviewEventType.RETRIEVING,
            ReviewEventType.REVIEWING,
            ReviewEventType.FINDING,
            ReviewEventType.FINDING,
            ReviewEventType.COMPLETED,
        ]
        assert events[-1]["data"]["score"] == SAMPLE_STRUCTURED_REVIEW.score  # type: ignore[index]

    async def test_finding_events_carry_each_finding(self, client: AsyncClient) -> None:
        job_id = await _start_review_job(client)

        events = _parse_sse_data((await client.get(f"/review/pr/{job_id}/events")).text)

        finding_titles = [
            event["data"]["title"]  # type: ignore[index]
            for event in events
            if event["type"] == ReviewEventType.FINDING
        ]
        assert finding_titles == ["Missing docstring", "Good use of type hints"]

    async def test_github_failure_streams_failed_with_message(
        self,
        client: AsyncClient,
        mock_github_service: MagicMock,
        mock_reviewer: MagicMock,
    ) -> None:
        mock_github_service.fetch_pr_diff.side_effect = PRNotFoundError(
            "Pull request not found"
        )
        job_id = await _start_review_job(client)

        events = _parse_sse_data((await client.get(f"/review/pr/{job_id}/events")).text)

        assert events == [
            {
                "id": events[0]["id"],
                "type": ReviewEventType.FAILED,
                "data": {"error": "Pull request not found"},
            }
        ]
        mock_reviewer.review_pr_with_context.assert_not_awaited()

    async def test_unexpected_failure_hides_real_message(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        mock_reviewer.review_pr_with_context = AsyncMock(
            side_effect=RuntimeError("secret internals")
        )
        job_id = await _start_review_job(client)

        events = _parse_sse_data((await client.get(f"/review/pr/{job_id}/events")).text)

        assert events[-1]["type"] == ReviewEventType.FAILED
        assert events[-1]["data"] == {"error": "Internal server error"}

    async def test_last_event_id_resumes_after_that_event(
        self, client: AsyncClient, mock_reviewer: MagicMock
    ) -> None:
        mock_reviewer.review_pr_with_context = AsyncMock(
            side_effect=_review_reporting_stages
        )
        job_id = await _start_review_job(client)
        url = f"/review/pr/{job_id}/events"
        all_events = _parse_sse_data((await client.get(url)).text)

        resumed = await client.get(
            url, headers={"Last-Event-ID": str(all_events[1]["id"])}
        )

        assert _parse_sse_data(resumed.text) == all_events[2:]

    async def test_unknown_job_returns_404(self, client: AsyncClient) -> None:
        response = await client.get(f"/review/pr/{uuid4()}/events")
        assert response.status_code == 404
