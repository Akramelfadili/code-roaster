import logging
import re
from typing import NamedTuple, NoReturn

import httpx

from app.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    InvalidPRUrlError,
    PRNotFoundError,
)

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 # nosec B105
GITHUB_DIFF_MEDIA_TYPE = "application/vnd.github.v3.diff"
_RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining"
_PR_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)/?$"
)


class PullRequestRef(NamedTuple):
    """Identifies a specific pull request on GitHub."""

    owner: str
    repo: str
    number: int


def _log_and_raise(exc: GitHubError) -> NoReturn:
    """Log a domain exception's type and message, then raise it."""
    logger.error("%s: %s", type(exc).__name__, exc)
    raise exc


def _log_failed_response(context: str, response: httpx.Response) -> None:
    """Log the status code and body of a failed GitHub API response."""
    logger.error(
        "%s failed: status=%d body=%s", context, response.status_code, response.text
    )


def _is_rate_limited(response: httpx.Response) -> bool:
    """Check whether a response indicates an exhausted GitHub rate limit."""
    is_forbidden = response.status_code == httpx.codes.FORBIDDEN
    remaining_exhausted = response.headers.get(_RATE_LIMIT_REMAINING_HEADER) == "0"
    return is_forbidden and remaining_exhausted


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
            _log_and_raise(
                InvalidPRUrlError(f"Not a valid GitHub pull request URL: {pr_url}")
            )
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
            logger.exception(
                "GitHub OAuth token exchange raised %s: %s", type(e).__name__, e
            )
            raise GitHubError("Failed to reach GitHub OAuth endpoint") from e

        if response.status_code != httpx.codes.OK:
            _log_failed_response("GitHub OAuth token exchange", response)
            if _is_rate_limited(response):
                _log_and_raise(GitHubRateLimitError("GitHub API rate limit exceeded"))
            _log_and_raise(
                GitHubAuthError(
                    f"GitHub OAuth token exchange failed: {response.status_code}"
                )
            )

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            _log_failed_response("GitHub OAuth token exchange", response)
            _log_and_raise(
                GitHubAuthError(data.get("error_description", "OAuth exchange failed"))
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
            logger.exception(
                "GitHub PR diff fetch for %s raised %s: %s",
                pr_label,
                type(e).__name__,
                e,
            )
            raise GitHubError("Failed to reach GitHub API") from e

        if response.status_code != httpx.codes.OK:
            _log_failed_response(f"GitHub PR diff fetch for {pr_label}", response)
            if _is_rate_limited(response):
                _log_and_raise(GitHubRateLimitError("GitHub API rate limit exceeded"))
            if response.status_code == httpx.codes.UNAUTHORIZED:
                _log_and_raise(GitHubAuthError("Invalid or expired GitHub token"))
            if response.status_code == httpx.codes.NOT_FOUND:
                _log_and_raise(PRNotFoundError(f"Pull request not found: {pr_label}"))
            _log_and_raise(GitHubError(f"GitHub API error: {response.status_code}"))
        return response.text
