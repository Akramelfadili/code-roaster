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

## Exceptions to "services never catch or log"
- **Streaming** (`CodeReviewer.review_stream`): once response bytes are flowing, `main.py` can't turn a failure into a clean JSON error, so the service logs with full context and re-raises
- **Background jobs** (`run_indexing_job`): the 202 is already sent, so it catches every failure, logs it, and records `AppError.client_message` (or `INTERNAL_SERVER_ERROR_MESSAGE` for unmodeled exceptions) on the job
