from unittest.mock import MagicMock

from httpx import AsyncClient

from app.exceptions import GitHubAuthError, InvalidPRUrlError, PRNotFoundError
from app.models.pr import PullRequestRef
from app.tests.mocks import SAMPLE_PR_DIFF, SAMPLE_PR_URL, SAMPLE_REPO_ID


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
