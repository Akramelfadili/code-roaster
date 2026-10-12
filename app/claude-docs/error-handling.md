# Backend Error Handling

- Never let raw exceptions reach the client
- Routes and services never catch exceptions and never log — they just raise. Logging and HTTP translation happen in exactly one place: `main.py`'s exception handlers
- All domain exceptions subclass `AppError` (`app/exceptions.py`). FastAPI resolves handlers by walking the exception's MRO, so the single `AppError` handler in `main.py` catches every subclass — **a new failure mode never needs a new handler**, just a new exception class
- Anything that isn't an `AppError` (an unmodeled bug) hits `unhandled_exception_handler` in `main.py`: logged at ERROR with a full traceback, returned as a generic 500 — never the real message
- If you're tempted to add `logger.error(...)` in a service or route, the failure needs a new or adjusted `AppError` subclass instead
- `main.py` calls `logging.basicConfig(...)` once at import time — don't remove it, and don't add a second call elsewhere

## Adding a domain exception
1. Subclass `AppError`, or an existing domain subclass (`GitHubError`, `ReviewError`) if it belongs there
2. Set `status_code` — required
3. Optionally override `log_level`: `logging.WARNING` for expected, user-fixable states (bad input, expired token, not found — no traceback); keep the `logging.ERROR` default for bugs and outages (full traceback)
4. Optionally override `user_message`: leave `None` to show the exception's own message; set a fixed string to hide it (infra failures whose detail isn't useful or safe to expose). `client_message` resolves which one the client sees
5. `raise SomeError("message")` — no logging call. Pass `debug_context="..."` for diagnostics (e.g. a raw API response body) that are logged but never sent to the client

## Model output and agent errors (V5)
Agent loops need typed failures, not generic 500s, so the loop (or the job runner) can tell what went wrong and react. All are `AppError`s with a fixed `user_message`.

| Exception | Status | Log | Raised when | Handling |
|---|---|---|---|---|
| `OutputTruncatedError` (`ReviewError`) | 500 | ERROR | `stop_reason == "max_tokens"` on any Claude call (`_raise_if_truncated` in `claude_client.py`) | Propagates — a partial review is never returned |
| `ToolExecutionError` | 200 | WARNING | An agent tool fails | **Never raised to the HTTP layer.** The loop catches it and sends `client_message` back to the model as a `tool_result` with `is_error=True` so the model can recover |
| `AgentStepLimitExceededError` | 429 | WARNING | A run hits its maximum step count | Ends the run |
| `BudgetExceededError` | 429 | WARNING | Today's spend has reached the daily cost budget (`CostBudget.ensure_available`, before every Claude and Voyage AI call) | Ends the run |
| `RunTimeoutError` | 504 | WARNING | A run exceeds its wall-clock limit | Ends the run |
| `RunCancelledError` | 499 | WARNING | A run is cancelled (499 = client closed request) | Ends the run |
| `ContextTooLargeError` | 413 | WARNING | The context a step would send exceeds the maximum size | Ends the run, unless the loop can trim the context and retry |

- **Check `stop_reason` after every Claude call.** `ClaudeClient` does this for every call (`_raise_if_truncated`, after usage is logged and charged); a new call path goes through `ClaudeClient` rather than repeating it
- Agent runs are review jobs (`ARCHITECTURE.md` §3.9), so a run-ending error reaches the client as `client_message` in the terminal `failed` event, not as an HTTP status

## Exceptions to "services never catch or log"
- **Streaming** (`ClaudeClient.stream_text`, behind `CodeReviewer.review_stream`): once response bytes are flowing, `main.py` can't turn a failure into a clean JSON error, so the service logs with full context and re-raises. This includes `OutputTruncatedError`, which can only be detected after the whole stream has been sent
- **Agent tools** (V5): the loop catches `ToolExecutionError` and returns it to the model as an `is_error` `tool_result` instead of raising
- **Retrieval** (`CodeRetriever.retrieve`): context is optional, so a query-embedding `AIProviderError` is logged at WARNING and returns `[]` — the review proceeds without context instead of failing
- **Background jobs** (`run_indexing_job`, `run_review_job`): the 202 is already sent, so they catch every failure, log it, and record `AppError.client_message` (or `INTERNAL_SERVER_ERROR_MESSAGE` for unmodeled exceptions) on the job. `run_review_job` also emits it as the terminal `failed` SSE event
