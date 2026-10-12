---
paths:
  - 'app/tests/**'
---

# Editing backend tests

The full conventions live in `app/claude-docs/testing.md`. Before adding or changing tests, check:
- Is the fixture or mock data you need already in `conftest.py` / `mocks.py`?
- Are services set on `app.state` directly? `ASGITransport` skips the lifespan
- Does every external call (Anthropic, GitHub, Voyage, Chroma) go through a mock, fake client, or `httpx.MockTransport`?
- Does the name follow `test_<what>_<expected_outcome>`, inside the endpoint's `Test*` class?
- Run `make test-back` before finishing
