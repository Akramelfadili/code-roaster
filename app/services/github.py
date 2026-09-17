import base64
import re
from pathlib import PurePosixPath
from typing import TypedDict, cast

import httpx

from app.constants import SUPPORTED_CODE_EXTENSIONS
from app.exceptions import (
    GitHubAuthError,
    GitHubError,
    InvalidPRUrlError,
    InvalidRepoUrlError,
    PRNotFoundError,
    RepoNotFoundError,
)
from app.models.pr import PullRequestRef
from app.services.github_errors import raise_for_github_response

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 # nosec B105
GITHUB_DIFF_MEDIA_TYPE = "application/vnd.github.v3.diff"
GITHUB_JSON_MEDIA_TYPE = "application/vnd.github+json"
_PR_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)/?$"
)
_REPO_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


class _TreeEntry(TypedDict):
    """The fields used from one entry of GitHub's recursive tree response."""

    path: str
    type: str
    sha: str


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

    async def fetch_repo_files(
        self, repo_url: str, token: str
    ) -> list[tuple[str, str]]:
        """Fetch every supported source file from a repository's default branch.

        Walks the repository's file tree and keeps only files whose extension
        is in `SUPPORTED_CODE_EXTENSIONS`, then fetches each one's content.

        Args:
            repo_url: HTTPS URL of the repository, e.g.
                `https://github.com/owner/repo`.
            token: GitHub access token.

        Returns:
            `(file_path, content)` tuples for every supported file, decoded as
            UTF-8. Files that cannot be decoded as UTF-8 (binary files) are
            skipped.

        Raises:
            InvalidRepoUrlError: If `repo_url` is not a valid GitHub repository
                URL.
            RepoNotFoundError: If the repository does not exist or is
                inaccessible with `token`.
            GitHubAuthError: On an invalid or expired token.
            GitHubRateLimitError: If GitHub's rate limit is exhausted.
            GitHubError: On any other GitHub API failure.
        """
        owner, repo = self._parse_repo_url(repo_url)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": GITHUB_JSON_MEDIA_TYPE,
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport, follow_redirects=True
            ) as client:
                branch = await self._fetch_default_branch(client, owner, repo, headers)
                entries = await self._fetch_source_tree(
                    client, owner, repo, branch, headers
                )
                return await self._fetch_blob_files(
                    client, owner, repo, entries, headers
                )
        except httpx.HTTPError as e:
            raise GitHubError("Failed to reach GitHub API") from e

    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """Extract owner and repo name from a GitHub repository URL."""
        match = _REPO_URL_PATTERN.match(repo_url.strip())
        if match is None:
            raise InvalidRepoUrlError(f"Not a valid GitHub repository URL: {repo_url}")
        return match["owner"], match["repo"]

    async def _fetch_default_branch(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        headers: dict[str, str],
    ) -> str:
        """Look up a repository's default branch name."""
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=headers
        )
        raise_for_github_response(
            f"GitHub repo fetch for {owner}/{repo}",
            response,
            not_found=RepoNotFoundError,
        )
        return str(response.json()["default_branch"])

    async def _fetch_source_tree(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        branch: str,
        headers: dict[str, str],
    ) -> list[_TreeEntry]:
        """Fetch the repo's full file tree, filtered to supported source files."""
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}",
            headers=headers,
            params={"recursive": "1"},
        )
        raise_for_github_response(f"GitHub tree fetch for {owner}/{repo}", response)
        entries = cast(list[_TreeEntry], response.json()["tree"])
        return [
            entry
            for entry in entries
            if entry["type"] == "blob"
            and PurePosixPath(entry["path"]).suffix in SUPPORTED_CODE_EXTENSIONS
        ]

    async def _fetch_blob_files(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        entries: list[_TreeEntry],
        headers: dict[str, str],
    ) -> list[tuple[str, str]]:
        """Fetch and decode each tree entry's blob content."""
        files: list[tuple[str, str]] = []
        for entry in entries:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/blobs/{entry['sha']}",
                headers=headers,
            )
            raise_for_github_response(
                f"GitHub blob fetch for {owner}/{repo}:{entry['path']}", response
            )
            raw_content = base64.b64decode(response.json()["content"])
            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            files.append((entry["path"], content))
        return files
