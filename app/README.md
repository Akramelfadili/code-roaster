# Code Roaster — Backend

FastAPI backend for AI-powered code review. All Claude API interaction lives here.

## Contents

```
app/
├── models/
│   └── review.py           # Pydantic request & response models
├── prompts/
│   └── review.py           # System prompts and the function-calling tool definition
├── routes/
│   └── review.py           # All route handlers — one router per domain
├── tests/
│   ├── conftest.py         # Shared fixtures: mock_reviewer, async client
│   ├── mocks.py            # Static mock data (SAMPLE_STRUCTURED_REVIEW, etc.)
│   └── test_routes.py      # Integration tests grouped by endpoint class
├── main.py                 # App factory, lifespan, router registration
├── reviewer.py             # CodeReviewer — all Anthropic SDK calls live here
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Dev dependencies (pytest, ruff, mypy, bandit, pre-commit)
└── pytest.ini              # asyncio_mode = auto, testpaths = tests
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key — loaded from `.env` at project root via `python-dotenv` |

Create `.env` in the **project root** (not inside `app/`):

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running Locally

Run from the **project root** with the conda environment active:

```bash
conda activate code-roaster
uvicorn app.main:app --reload
```

- API base: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

---

## API Endpoints

### `POST /review`

One-shot review. Waits for the full response before returning.

**Request**
```json
{
  "code": "def add(a, b):\n    return a + b",
  "language": "python"
}
```

**Response** `200 OK`
```json
{
  "review": "The function is correct but lacks type hints..."
}
```

---

### `POST /review/stream`

Streaming review. Returns plain text chunks via `StreamingResponse` as Claude generates them.

**Request** — same shape as `/review`

**Response** `200 OK` — `Content-Type: text/plain`, body streamed incrementally

---

### `POST /review/structured`

Structured review via Claude function calling. Forces the model to populate a typed schema.

**Request** — same shape as `/review`

**Response** `200 OK`
```json
{
  "summary": "Overall decent code with one critical security issue.",
  "severity": "high",
  "score": 6,
  "bugs": ["Off-by-one error in loop on line 12"],
  "security_issues": ["User input passed directly to SQL query"],
  "suggestions": ["Add input validation", "Use parameterised queries"],
  "positives": ["Clear variable names", "Good separation of concerns"]
}
```

`severity` is one of: `"low"` | `"medium"` | `"high"` | `"critical"`
`score` is an integer `1–10`

---

### `GET /health`

**Response** `200 OK`
```json
{ "status": "ok" }
```

---

### Error responses

All review endpoints return `422` if `code` is empty or whitespace-only:

```json
{ "detail": "Code must not be empty" }
```

---

## Running Tests

```bash
conda activate code-roaster
make test-back
# or directly:
cd app && pytest
```

- `asyncio_mode = auto` in `pytest.ini` — no `@pytest.mark.asyncio` needed on test functions
- The Anthropic client is **always mocked** — no real API calls, no key required
- `ASGITransport` skips the FastAPI lifespan, so `app.state.reviewer` is set directly in the `client` fixture
- `review_stream` is a `MagicMock(side_effect=async_gen_fn)` — not an `AsyncMock` — because it returns an async generator, not a coroutine

---

## Code Quality

Run individually or all at once via `make check-all`.

### Lint

```bash
make lint-back
# or: ruff check app/
```

### Format

```bash
make format-back
# or: ruff format app/
```

Mutates files. Run before committing if pre-commit hasn't auto-fixed.

### Type check

```bash
make type-back
# or: mypy app/
```

Strict mode (`strict = true`, `python_version = 3.12` in `mypy.ini`). No `Any`, explicit return types on everything.

### Security scan

```bash
make security-back
# or: bandit -r app/ -c .bandit --exclude app/tests
```

Skips `app/tests/` — `S101` (assert usage) is expected in test code.

### All checks

```bash
make check-all
```

Runs lint + type check + security scan across both backend and frontend. Does not run `format-back` since it mutates files.

---

## Key Design Decisions

**`CodeReviewer` owns all AI logic.** Routes call `reviewer.review*()` methods only — no Anthropic SDK imports in route handlers. This keeps the routes testable without touching the API.

**Prompt caching on every call.** All system prompts include `"cache_control": {"type": "ephemeral"}` to reduce latency and token cost on repeated reviews.

**`AsyncAnthropic` only.** The sync client is never used. All three reviewer methods are `async` — `review` and `review_structured` use `await client.messages.create()`, `review_stream` uses `async with client.messages.stream()`.

**Lifespan for startup.** `CodeReviewer` is instantiated once in the FastAPI lifespan and stored on `app.state`. Routes access it via `req.app.state.reviewer`. No global state, no singletons.
