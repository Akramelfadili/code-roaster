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

**Naming:** `test_<what>_<expected_outcome>` — e.g. `test_empty_code_returns_422`

**Grouping:** one class per endpoint — `class TestReviewStream`, `class TestReviewStructured`
