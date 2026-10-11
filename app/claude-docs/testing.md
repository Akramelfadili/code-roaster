# Backend Testing

**Stack:** `pytest`, `pytest-asyncio`, `httpx` — install from `app/requirements-dev.txt`

**Run:** `make test-back` (runs `cd app && pytest`; `pytest.ini` sets `testpaths = tests`)

**Layout:** one `test_<module>.py` per route module or service (`routes/pr.py` → `test_pr.py`, `services/github.py` → `test_github_service.py`). Shared fixtures live in `conftest.py`, shared mock data in `mocks.py` — never duplicate a fixture inside a test file.

**Async:** `asyncio_mode = auto` — no `@pytest.mark.asyncio` needed.

**Mocking the Anthropic client:**
- Never instantiate a real `CodeReviewer` — it requires `ANTHROPIC_API_KEY` and hits the API
- `ASGITransport` does NOT trigger the FastAPI lifespan, so set `app.state.reviewer` (and other services) directly in the fixture
- Base: `MagicMock(spec=CodeReviewer)`; `review_structured` as `AsyncMock`; `review_stream` as `MagicMock(side_effect=async_gen_fn)` — it returns an async generator, not a coroutine

**Mocking GitHub calls:**
- Never hit the real GitHub API
- Route level: `MagicMock(spec=GitHubService)` via the `mock_github_service` fixture, set on `app.state.github_service` in the `client` fixture
- Service level: inject `httpx.MockTransport(handler)` via `GitHubService(..., transport=...)` and assert on returned data or the raised domain exception

**Database (Postgres):**
- Tests that touch the DB (`test_index.py`, `test_indexing_jobs.py`, `test_review_jobs.py`, and the `TestReviewPrAsync` / `TestReviewPrEvents` classes in `test_pr.py`) use the `db_session_factory` fixture. It drops and recreates every table on `TEST_DATABASE_URL` with `create_all` (fast; `alembic check` guards against drift from the migrations), then sets `app.state.session_factory` — same pattern as the mocked services
- Without `TEST_DATABASE_URL` those tests are **skipped**, not failed; everything else runs with no database
- `TEST_DATABASE_URL` must be a separate, disposable database — it is wiped on every test. Never point it at `DATABASE_URL`'s database
- `DATABASE_URL` must still be set (any value works) — importing `app.main` builds `Settings`, but no test connects to it
- One-time setup, then run:
  ```bash
  createdb -h localhost -U postgres code_roaster_test   # or: psql -c 'CREATE DATABASE code_roaster_test'
  # .env: TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/code_roaster_test
  make test-back
  ```

**SSE endpoints:**
- `BackgroundTasks` finish before `ASGITransport` returns the `202`, so by the time the test opens the stream every event is already written. A plain `await client.get(...)` reads the whole stream, and the stream ends on the terminal event
- Parse `response.text` by its `data: ` lines (`_parse_sse_data` in `test_pr.py`). To emit stage events from the mocked reviewer, give `review_pr_with_context` a `side_effect` that awaits `on_stage`
- To test following a live job, run `stream_review_events` in an `asyncio.Task` and write events while it runs. Monkeypatch `review_jobs._EVENT_POLL_INTERVAL_SECONDS` down to keep the test fast

**Naming:** `test_<what>_<expected_outcome>` — e.g. `test_empty_code_returns_422`

**Grouping:** one class per endpoint — `class TestReviewStream`, `class TestReviewStructured`
