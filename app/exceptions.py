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

    @property
    def client_message(self) -> str:
        """The message safe to show the client: `user_message`, else our own."""
        return self.user_message if self.user_message is not None else str(self)


class ReviewError(AppError):
    status_code = 500


class AIProviderError(ReviewError):
    status_code = 502
    user_message: str | None = "AI provider unavailable"


class AIProviderRateLimitError(AIProviderError):
    status_code = 429
    log_level = logging.WARNING
    user_message: str | None = None


class OutputTruncatedError(ReviewError):
    """Claude stopped at `max_tokens`, so the review it returned is partial."""

    status_code = 500
    user_message: str | None = "Review output was truncated. Try with a smaller input."


class ReviewJobNotFoundError(ReviewError):
    status_code = 404
    log_level = logging.WARNING


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


class InvalidRepoUrlError(GitHubError):
    status_code = 400
    log_level = logging.WARNING
    user_message = None


class RepoNotFoundError(GitHubError):
    status_code = 404
    log_level = logging.WARNING
    user_message = None


class GitHubRateLimitError(GitHubError):
    status_code = 429
    log_level = logging.WARNING
    user_message = None


class IndexingError(AppError):
    status_code = 500


class IndexingJobNotFoundError(IndexingError):
    status_code = 404
    log_level = logging.WARNING


class IndexingAlreadyInProgressError(IndexingError):
    status_code = 409
    log_level = logging.WARNING


class VectorStoreError(AppError):
    status_code = 500
    user_message: str | None = "Vector store unavailable"


class BudgetExceededError(AppError):
    """A request would push spend past the daily cost budget."""

    status_code = 429
    log_level = logging.WARNING
    user_message: str | None = "Request exceeds cost budget."


class ToolExecutionError(AppError):
    """An agent tool failed. Never raised to the HTTP layer.

    The agent loop catches it and returns `client_message` to the model as a
    `tool_result` with `is_error=True`, so the model can recover. The 200
    status only applies if it ever reaches `main.py` by mistake.
    """

    status_code = 200
    log_level = logging.WARNING
    user_message: str | None = "Tool execution failed."


class AgentStepLimitExceededError(AppError):
    """An agent run used up its maximum number of loop steps."""

    status_code = 429
    log_level = logging.WARNING
    user_message: str | None = "Agent reached maximum step limit."


class RunTimeoutError(AppError):
    """An agent run exceeded its wall-clock time limit."""

    status_code = 504
    log_level = logging.WARNING
    user_message: str | None = "Agent run timed out."


class RunCancelledError(AppError):
    """An agent run was cancelled before finishing (499: client closed request)."""

    status_code = 499
    log_level = logging.WARNING
    user_message: str | None = "Agent run was cancelled."


class ContextTooLargeError(AppError):
    """The context an agent step would send exceeds the maximum size."""

    status_code = 413
    log_level = logging.WARNING
    user_message: str | None = "Context exceeds maximum size."
