import httpx
import pytest

from app.exceptions import (
    GitHubAuthError,
    GitHubRateLimitError,
    InvalidPRUrlError,
    PRNotFoundError,
)
from app.services.github import GitHubService, PullRequestRef
from app.tests.mocks import SAMPLE_PR_REF, SAMPLE_PR_URL


def _make_service(handler: httpx.MockTransport) -> GitHubService:
    return GitHubService(
        client_id="mock-client-id",
        client_secret="mock-secret",  # noqa: S106
        transport=handler,
    )


class TestParsePrUrl:
    def test_valid_url_returns_pr_ref(self) -> None:
        service = GitHubService(client_id="id", client_secret="secret")  # noqa: S106
        assert service.parse_pr_url(SAMPLE_PR_URL) == SAMPLE_PR_REF

    def test_invalid_url_raises(self) -> None:
        service = GitHubService(client_id="id", client_secret="secret")  # noqa: S106
        with pytest.raises(InvalidPRUrlError):
            service.parse_pr_url("https://example.com/not-a-pr")


class TestExchangeCodeForToken:
    async def test_happy_path_returns_token(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"access_token": "abc123"})

        service = _make_service(httpx.MockTransport(handler))
        token = await service.exchange_code_for_token("some-code")
        assert token == "abc123"  # noqa: S105

    async def test_missing_token_raises_auth_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"error": "bad_verification_code"})

        service = _make_service(httpx.MockTransport(handler))
        with pytest.raises(GitHubAuthError):
            await service.exchange_code_for_token("bad-code")


class TestFetchPrDiff:
    async def test_happy_path_returns_diff(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="diff --git a/f b/f")

        service = _make_service(httpx.MockTransport(handler))
        pr = PullRequestRef(owner="octocat", repo="hello-world", number=42)
        diff = await service.fetch_pr_diff(pr, "token")
        assert "diff --git" in diff

    async def test_unauthorized_raises_auth_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"message": "Bad credentials"})

        service = _make_service(httpx.MockTransport(handler))
        pr = PullRequestRef(owner="octocat", repo="hello-world", number=42)
        with pytest.raises(GitHubAuthError):
            await service.fetch_pr_diff(pr, "bad-token")

    async def test_not_found_raises_pr_not_found_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "Not Found"})

        service = _make_service(httpx.MockTransport(handler))
        pr = PullRequestRef(owner="octocat", repo="hello-world", number=999)
        with pytest.raises(PRNotFoundError):
            await service.fetch_pr_diff(pr, "token")

    async def test_rate_limit_raises_rate_limit_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"message": "rate limit"},
                headers={"X-RateLimit-Remaining": "0"},
            )

        service = _make_service(httpx.MockTransport(handler))
        pr = PullRequestRef(owner="octocat", repo="hello-world", number=42)
        with pytest.raises(GitHubRateLimitError):
            await service.fetch_pr_diff(pr, "token")
