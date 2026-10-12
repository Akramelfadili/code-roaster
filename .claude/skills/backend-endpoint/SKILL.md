---
name: backend-endpoint
description: Scaffold a complete Code Roaster FastAPI endpoint end to end — Pydantic models, AppError subclass, service function, thin route, constants, Alembic migration if the schema changes, and pytest tests using the existing conftest fixtures — then verify it and prepare one conventional commit. Use whenever the user types /backend-endpoint, or asks to add, create, scaffold or wire up a backend endpoint, route or API for this project ("add a GET /x that...", "scaffold an endpoint for X", "expose X over the API", "I need a route that returns..."), even if they only describe the behaviour and never say "endpoint".
---

# Backend endpoint scaffolding (Code Roaster)

The goal is an endpoint the user could have written themselves: it sits in the right files, reuses what's already there, passes `make lint-back type-back test-back`, and comes with one commit. Most mistakes in this codebase come from building exactly what the request says when the request assumes something the code doesn't have. Step 1 exists to catch that.

## Constraints

- Never change the behavior of an existing endpoint. If the feature requires it, stop and ask the user to confirm before proceeding.

## Step 0: Load the conventions

The rules live in the repo. Read them instead of relying on memory, because they change:

- `app/CLAUDE.md`: structure, FastAPI, Database, Input Caps
- `app/claude-docs/error-handling.md`: the AppError rules
- `app/claude-docs/testing.md`: fixtures, DB tests, naming
- The **closest existing endpoint, end to end** (route → service → model → test). Pick it by shape:

| New endpoint looks like | Copy the shape of |
|---|---|
| Reads or writes Postgres rows | `routes/index.py` → `services/indexing_jobs.py` → `models/index.py` → `tests/test_index.py` |
| Starts background work and returns 202 | `POST /index/repo` or `POST /review/pr/async` |
| Streams (SSE) | `GET /review/pr/{job_id}/events` (uses `FunctionScopedDbSession`) |
| Calls Claude | `routes/review.py` → `services/reviewer.py` → `services/claude_client.py` |
| Calls GitHub | `routes/pr.py` → `services/github.py` (+ `github_errors.py`) |

Before adding anything new, grep for it. There may already be a service function, an exception or a constant you can reuse, such as `get_review_job`, `REPO_ID_SEPARATOR` or `IndexingJobNotFoundError`.

## Step 1: Check the request against the codebase before writing code

Compare each assumption in the request with what the code actually has. Common gaps:

- **Identity / "current user" / "my".** The backend has **no user model and no auth dependency**. The GitHub token arrives in the request body per call (`github_token` on `IndexRepoRequest` / `PRReviewRequest`), and no table records who created a row. A request scoped to the user therefore needs a design decision, and code alone can't settle it. Options include:
  - resolving the token to a GitHub login and adding an owner column (schema change + migration)
  - filtering by what the token can access on GitHub (an extra API call)
  - dropping the scoping

  Never fake it, for example by returning everything under a "for current user" docstring. An endpoint that quietly leaks every row is worse than no endpoint.
- **HTTP method and status.** Reads are `GET`. Creation is `POST` with 201, or 202 if the work runs in the background. If the request names a method that doesn't fit, point it out. One legitimate exception here: a read that needs the GitHub token uses `POST` with a body, because the codebase sends tokens in bodies, never in query strings, where they end up in logs.
- **Which router.** There is one router per domain (`review`, `auth`, `pr`, `index`, `health`). A new path under an existing domain goes on that router. A genuinely new domain gets a new router, an `include_router` call in `main.py`, and a line in `app/CLAUDE.md`'s structure tree.
- **Does the data exist?** If the response needs a field no table stores, that's a schema change, and it ships with an Alembic migration.
- **Unbounded results.** A list endpoint over a growing table needs a limit. Use a named constant, plus pagination if the user wants it.

**What to do with gaps:** if the user is available, ask before writing code. Put the gaps in one short message with a recommended option for each. If you were told to proceed without questions, pick the option that is honest and least invasive, then state each assumption clearly in your final report so the user can redirect you.

## Step 2: Put each piece where it belongs

| Piece | Location | Rules that are easy to miss |
|---|---|---|
| Request/response models | `app/models/<domain>.py`, exported from `app/models/__init__.py` (`__all__`) | Pydantic v2. Validation goes in `field_validator` / `Field(max_length=...)`, never in the route. Docstrings on classes. Client-supplied strings that reach an LLM or embedding need a `MAX_*` cap |
| ORM table (only if needed) | `app/models/db/<domain>.py`, imported in `app/models/db/__init__.py` | `StrEnum` stored via `values_callable=enum_values`; `DateTime(timezone=True)`; invariants as indexes/constraints. **Plus a migration**: `alembic revision --autogenerate -m "..."`, reviewed, literals only |
| Service | `app/services/<domain>.py`. DB work is module-level `async def f(session: AsyncSession, ...)` functions like `indexing_jobs.py`; external-API work is a method on the existing service class | All DB access lives here. Map rows to Pydantic models in a private `_to_<model>` helper, so routes never see ORM objects. Raise domain exceptions; never catch, never log. Translate actionable DB errors (`IntegrityError` → a 409 `AppError`) |
| Exception (only if needed) | `app/exceptions.py`, under the domain's base (`IndexingError`, `ReviewError`, `GitHubError`) | Set `status_code`, plus `log_level = logging.WARNING` for user-fixable states (404/409/400). No handler: `main.py`'s `AppError` handler covers every subclass. An empty list is a 200 `[]`, not a 404 |
| Route | `app/routes/<domain>.py` | Thin: parse → call service → return. `response_model=` and an explicit return type. Sessions via `db: DbSession`. Services from `req.app.state.<service>`, which the lifespan puts there; don't invent `Depends` providers for them. Docstring on the handler |
| Constants | `app/constants.py` **only if used by more than one module**; otherwise module-level `_PRIVATE` in the file that uses it | No magic strings or numbers, including limits, path fragments and messages |
| Tests | `app/tests/test_<route module>.py` (route level) and `test_<service>.py` (service level) | See Step 3 |

House rules from the root CLAUDE.md that apply to every file:
- Functions under about 20 lines with a single responsibility; split helpers out
- Descriptive names
- Absolute `from app...` imports
- Docstrings on public functions and classes
- No commented-out code
- No `Any`; mypy is strict

## Step 3: Tests

- **Use the fixtures in `conftest.py`:** `client`, `mock_reviewer`, `mock_github_service`, `mock_indexer`, `db_session_factory`. Shared sample data goes in `mocks.py` (`SAMPLE_REPO_ID`, `SAMPLE_REPO_URL`, ...). Add new shared samples there rather than redefining them in a test file. If a new service needs mocking at the route level, add a fixture to `conftest.py` and set it on `app.state` in `client`.
- **DB-backed tests:** `pytestmark = pytest.mark.usefixtures("db_session_factory")` at module level, or on the class if other classes in the file don't need the DB. Seed rows directly through `db_session_factory()` sessions, as `test_index.py` does.
- **Structure:** one `class Test<Endpoint>` per endpoint. Names follow `test_<what>_<expected_outcome>`. No `@pytest.mark.asyncio`, because `asyncio_mode = auto` is set.
- **Cover:**
  - the happy path, asserting on the response shape
  - the empty case
  - each validation failure (422)
  - each domain error the endpoint can raise, with its status
  - anything that must *not* leak, such as tokens or other users' rows
  - the specific query semantics (ordering, "latest per X", limits)

## Step 4: Verify

Run from the project root, in the `code-roaster` conda env:

```bash
make format-back && make lint-back && make type-back && make security-back && make test-back
```

- If `make test-back` fails on a missing `DATABASE_URL`, set any value inline (`DATABASE_URL=postgresql+asyncpg://x:x@localhost/x make test-back`). Tests never connect to it.
- Without `TEST_DATABASE_URL`, DB-backed tests are **skipped, not run**. Check the pytest summary for your new tests. If they were skipped, say so plainly in the report. "All checks pass" would be misleading when the endpoint's core query never executed.
- If the schema changed and a database is reachable, also run `alembic upgrade head` and `alembic check`.

Fix what fails. Don't use `--no-verify` or `# type: ignore` to get around a real error.

## Step 5: Documentation

Update `app/CLAUDE.md` when the structure tree changes (new module, router or table) or a new convention appears. Update `ARCHITECTURE.md` if you made a design decision, such as introducing user identity or ownership. Otherwise leave docs alone.

## Step 6: Commit

- Never commit to `main`. If needed, create `feature/<short-name>` (or `fix/`, `refactor/`).
- **Before committing, show the user the file list and the commit message, and wait for approval.** The project requires this. If you were told not to wait, write the message out and leave the changes staged.
- One commit. Conventional message, e.g. `feat: add GET /index/repos listing indexed repositories`, with a body that explains anything non-obvious, such as the assumptions from Step 1.
- Never push.

## Final report

Keep it short and cover:
- **Endpoint:** method, path, request and response shape
- **Files:** each file touched, one line each
- **Assumptions and open questions** from Step 1, especially anything about identity or scoping
- **Checks:** the exact results, including how many new tests passed vs. were skipped
- **Commit:** the proposed message
