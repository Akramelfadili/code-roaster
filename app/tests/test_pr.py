from unittest.mock import MagicMock

from httpx import AsyncClient

from app.exceptions import GitHubAuthError, InvalidPRUrlError, PRNotFoundError
from app.tests.mocks import SAMPLE_PR_URL


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
