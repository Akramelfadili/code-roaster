import httpx

from app.exceptions import AppError, GitHubAuthError, GitHubError, GitHubRateLimitError

_RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining"


def is_rate_limited(response: httpx.Response) -> bool:
    """Check whether a response indicates an exhausted GitHub rate limit."""
    is_forbidden = response.status_code == httpx.codes.FORBIDDEN
    remaining_exhausted = response.headers.get(_RATE_LIMIT_REMAINING_HEADER) == "0"
    return is_forbidden and remaining_exhausted


def raise_for_github_response(
    context: str,
    response: httpx.Response,
    *,
    not_found: type[AppError] | None = None,
    default: type[AppError] = GitHubError,
) -> None:
    """Translate a failed GitHub API response into the matching domain exception.

    This is the single place that maps a GitHub HTTP response to a domain
    exception, so every `GitHubService` method that makes an API call goes
    through it instead of hand-rolling its own status-code branching.
    Raising is the only job here — logging happens once, centrally, in
    `main.py`'s `AppError` handler, using each exception's `debug_context`
    (the response status and body, attached below) for extra detail.

    No-ops on a 200 OK response. Otherwise raises, in priority order:

    1. `GitHubRateLimitError`, if the response signals an exhausted rate
       limit (see `is_rate_limited`).
    2. `GitHubAuthError`, on a 401 (invalid or expired token/credentials).
       This check is unconditional because "unauthorized" means the same
       thing for every GitHub endpoint.
    3. `not_found`, on a 404 — only checked when the caller supplies a type.
       "Not found" only makes sense for calls that fetch a specific resource
       (e.g. a pull request); callers that don't fetch a resource, like the
       OAuth token exchange, should leave this unset. Note GitHub also
       returns 404 (not 403) when the caller lacks access to a private
       resource, to avoid confirming it exists.
    4. `default` for any other status code (falls back to `GitHubError`).

    Args:
        context: Human-readable description of the call, used in the
            exception message raised for case 3.
        response: The `httpx.Response` to inspect.
        not_found: Exception type to raise on 404. Omit for endpoints where
            "not found" isn't a meaningful outcome.
        default: Exception type to raise for any status code not covered by
            cases 1-3.
    """
    if response.status_code == httpx.codes.OK:
        return
    debug_context = f"status={response.status_code} body={response.text}"
    if is_rate_limited(response):
        raise GitHubRateLimitError(
            "GitHub API rate limit exceeded", debug_context=debug_context
        )
    if response.status_code == httpx.codes.UNAUTHORIZED:
        raise GitHubAuthError(
            "Invalid or expired GitHub token", debug_context=debug_context
        )
    if not_found is not None and response.status_code == httpx.codes.NOT_FOUND:
        raise not_found(f"{context}: not found", debug_context=debug_context)
    raise default(
        f"GitHub API error: {response.status_code}", debug_context=debug_context
    )
