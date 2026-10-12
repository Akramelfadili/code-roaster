from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient

from app.routes.auth import OAUTH_STATE_COOKIE_NAME


async def _start_login(client: AsyncClient) -> str:
    """Hit the login endpoint and return the state GitHub would echo back."""
    response = await client.get("/auth/github", follow_redirects=False)
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["state"][0]


class TestGithubLogin:
    async def test_redirects_to_github_oauth_page(self, client: AsyncClient) -> None:
        response = await client.get("/auth/github", follow_redirects=False)
        assert response.status_code in (302, 307)
        assert "github.com/login/oauth/authorize" in response.headers["location"]

    async def test_state_param_matches_httponly_state_cookie(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/auth/github", follow_redirects=False)
        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["state"][0] == response.cookies[OAUTH_STATE_COOKIE_NAME]
        assert "httponly" in response.headers["set-cookie"].lower()

    async def test_each_login_generates_a_fresh_state(
        self, client: AsyncClient
    ) -> None:
        assert await _start_login(client) != await _start_login(client)


class TestGithubCallback:
    async def test_happy_path_redirects_with_token_in_fragment(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        state = await _start_login(client)
        response = await client.get(
            "/auth/github/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert response.headers["location"] == (
            "http://localhost:5173/auth/callback#token=mock-access-token"
        )
        mock_github_service.exchange_code_for_token.assert_awaited_once_with("abc")

    async def test_happy_path_clears_state_cookie(self, client: AsyncClient) -> None:
        state = await _start_login(client)
        await client.get(
            "/auth/github/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert OAUTH_STATE_COOKIE_NAME not in client.cookies

    async def test_mismatched_state_returns_401(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        await _start_login(client)
        response = await client.get(
            "/auth/github/callback",
            params={"code": "abc", "state": "forged-state"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        mock_github_service.exchange_code_for_token.assert_not_awaited()

    async def test_missing_state_cookie_returns_401(
        self, client: AsyncClient, mock_github_service: MagicMock
    ) -> None:
        response = await client.get(
            "/auth/github/callback",
            params={"code": "abc", "state": "some-state"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        mock_github_service.exchange_code_for_token.assert_not_awaited()

    async def test_missing_code_returns_422(self, client: AsyncClient) -> None:
        response = await client.get(
            "/auth/github/callback", params={"state": "some-state"}
        )
        assert response.status_code == 422

    async def test_missing_state_returns_422(self, client: AsyncClient) -> None:
        response = await client.get("/auth/github/callback", params={"code": "abc"})
        assert response.status_code == 422
