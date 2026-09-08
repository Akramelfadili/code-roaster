import re

import httpx

from app.exceptions import (
    GitHubAuthError,
    GitHubError,
    InvalidPRUrlError,
    PRNotFoundError,
)
from app.models.pr import PullRequestRef
from app.services.github_errors import raise_for_github_response

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 # nosec B105
GITHUB_DIFF_MEDIA_TYPE = "application/vnd.github.v3.diff"
_PR_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)/?$"
)


class GitHubService:
    """Handles GitHub OAuth token exchange and pull request diff retrieval."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._transport = transport

    def parse_pr_url(self, pr_url: str) -> PullRequestRef:
        """Extract owner, repo, and PR number from a GitHub pull request URL."""
        match = _PR_URL_PATTERN.match(pr_url.strip())
        if match is None:
            raise InvalidPRUrlError(f"Not a valid GitHub pull request URL: {pr_url}")
        return PullRequestRef(
            owner=match["owner"], repo=match["repo"], number=int(match["number"])
        )

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange an OAuth authorization code for a GitHub access token."""
        try:
            async with httpx.AsyncClient(transport=self._transport) as client:
                response = await client.post(
                    GITHUB_OAUTH_TOKEN_URL,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                    },
                )
        except httpx.HTTPError as e:
            raise GitHubError("Failed to reach GitHub OAuth endpoint") from e

        raise_for_github_response(
            "GitHub OAuth token exchange", response, default=GitHubAuthError
        )

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            raise GitHubAuthError(
                data.get("error_description", "OAuth exchange failed")
            )
        return str(access_token)

    async def fetch_pr_diff(self, pr: PullRequestRef, token: str) -> str:
        """Fetch the unified diff for a pull request from the GitHub API."""
        pr_label = f"{pr.owner}/{pr.repo}#{pr.number}"
        url = f"{GITHUB_API_BASE}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}"
        try:
            async with httpx.AsyncClient(
                transport=self._transport, follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": GITHUB_DIFF_MEDIA_TYPE,
                    },
                )
        except httpx.HTTPError as e:
            raise GitHubError("Failed to reach GitHub API") from e

        raise_for_github_response(
            f"GitHub PR diff fetch for {pr_label}", response, not_found=PRNotFoundError
        )
        return response.text
