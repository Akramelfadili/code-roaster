from unittest.mock import MagicMock

from httpx import AsyncClient


class TestGithubLogin:
    async def test_redirects_to_github_oauth_page(self, client: AsyncClient) -> None:
        response = await client.get("/auth/github", follow_redirects=False)
        assert response.status_code in (302, 307)
        assert "github.com/login/oauth/authorize" in response.headers["location"]


class TestGithubCallback:
    async def test_happy_path_redirects_with_access_token(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        response = await client.get(
            "/auth/github/callback", params={"code": "abc"}, follow_redirects=False
        )
        assert response.status_code in (302, 307)
        assert response.headers["location"] == (
            "http://localhost:5173/auth/callback?token=mock-access-token"
        )
        mock_github_service.exchange_code_for_token.assert_awaited_once_with("abc")

    async def test_missing_code_returns_422(self, client: AsyncClient) -> None:
        response = await client.get("/auth/github/callback")
        assert response.status_code == 422
