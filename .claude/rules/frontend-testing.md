---
paths:
  - 'frontend/src/tests/**'
---

# Editing frontend tests

The full conventions live in `frontend/claude-docs/testing.md`. Before adding or changing tests, check:
- Does the file mirror its `src/` path under `src/tests/`, using `.tsx` only when it renders JSX?
- Is the API mocked at the `@/api/` boundary, so no fetch reaches the network?
- Do hook tests use a fresh `QueryClientProvider` per test?
- Do assertions target behaviour, not class names or snapshots?
- Run `make test-front` before finishing

@../../frontend/claude-docs/testing.md
