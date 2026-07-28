import logging


class AppError(Exception):
    """Base for every domain exception the API can turn into an HTTP response.

    A single handler in `main.py` catches `AppError` (and, since FastAPI
    resolves exception handlers by walking the exception's MRO, every
    subclass too) and uses these class attributes to log and respond —
    no per-exception-type handler function is needed. Subclasses only need
    to declare `status_code`; the rest have sane defaults:

    - `status_code`: HTTP status returned to the client.
    - `log_level`: severity to log at. Use `logging.WARNING` for expected,
      user-fixable states (bad input, expired token, not found) and
      `logging.ERROR` (the default) for anything that signals a bug or an
      outage — `ERROR`-and-above also gets a full traceback attached.
    - `user_message`: overrides what the client sees. Leave as `None` to
      show the exception's own message (safe for expected, actionable
      errors); set a fixed string to hide the real message instead (for
      unexpected/infra failures where the internal detail isn't useful, or
      safe, to expose).
    - `debug_context`: optional extra diagnostic detail passed at raise
      time (e.g. a raw API response body). Logged alongside the message,
      never sent to the client.
    """

    status_code: int = 500
    log_level: int = logging.ERROR
    user_message: str | None = None

    def __init__(self, message: str, *, debug_context: str | None = None) -> None:
        super().__init__(message)
        self.debug_context = debug_context


class ReviewError(AppError):
    status_code = 500


class AIProviderError(ReviewError):
    status_code = 502
    user_message: str | None = "AI provider unavailable"


class MalformedAIResponseError(ReviewError):
    status_code = 500
    user_message: str | None = "Unexpected response from AI"


class GitHubError(AppError):
    status_code = 502
    user_message: str | None = "GitHub API unavailable"


class InvalidPRUrlError(GitHubError):
    status_code = 400
    log_level = logging.WARNING
    user_message = None


class GitHubAuthError(GitHubError):
    status_code = 401
    log_level = logging.WARNING
    user_message = None


class PRNotFoundError(GitHubError):
    status_code = 404
    log_level = logging.WARNING
    user_message = None


class GitHubRateLimitError(GitHubError):
    status_code = 429
    log_level = logging.WARNING
    user_message = None
