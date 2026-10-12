# Code Roaster — CLAUDE.md (Global)

## Project Overview
AI-powered code review tool. Users either paste code directly or connect their GitHub account and submit a pull request URL — either way, they get a structured review with a score and lists of findings (bugs, security issues, suggestions, positives). Each finding is a structured `Finding` object with a title, explanation, confidence and, when locatable, a file and line range — see ARCHITECTURE.md §3.7. Built by a full stack dev learning AI engineering.

## Tech Stack
- **Backend:** Python, FastAPI, Anthropic SDK (Claude Sonnet)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, React Query
- **AI:** Claude API (streaming + function calling)
- **Package manager:** conda (backend), npm (frontend)

## Project Structure
```
code-roaster/
├── app/          # FastAPI backend — see app/CLAUDE.md for structure and conventions
├── frontend/     # React frontend — see frontend/CLAUDE.md for structure and conventions
├── docs/         # Architecture diagrams (Excalidraw)
└── README.md
```

## Commands

All commands run from the project root via `make`.

| Command | What it does |
|---|---|
| `make run` | Run backend and frontend together (honcho, via `Procfile`) |
| `make run-back` | Run the FastAPI backend with auto-reload (`uvicorn app.main:app --reload`) |
| `make run-front` | Run the Vite dev server |
| `make dev` | Start the dev Postgres (Docker Compose), then the backend with auto-reload |
| `make db-up` | Start the dev Postgres in the background (`localhost:5432`, persisted in the `postgres_data` volume) |
| `make db-down` | Stop all Compose containers (dev data is kept) |
| `make db-reset` | Delete the dev Postgres volume and start a fresh, empty database |
| `make db-test-up` | Start the ephemeral test Postgres (`localhost:5433`, no volume) for `TEST_DATABASE_URL` |
| `make db-migrate` | Run `alembic upgrade head` against `DATABASE_URL` (needs `db-up` first) |
| `make db-shell` | Open `psql` in the running dev Postgres container |
| `make lint-back` | Ruff lint check on `app/` |
| `make format-back` | Ruff format `app/` (mutates files) |
| `make type-back` | Mypy strict type check on `app/` |
| `make security-back` | Bandit security scan on `app/` |
| `make test-back` | Pytest suite in `app/tests/` |
| `make lint-front` | ESLint on `frontend/src/` (`npm run lint`) |
| `make format-front` | Prettier format check on `frontend/src/` |
| `make type-front` | TypeScript type check (`tsc -b tsconfig.app.json --noEmit`) |
| `make test-front` | Vitest suite in `frontend/` |
| `make check-all` | Runs all checks (no format-back — it mutates) |

- Backend tests need `DATABASE_URL` in `.env` (any value) or collection fails entirely; DB tests are skipped without `TEST_DATABASE_URL` (start it with `make db-test-up`). Always report pass/skip/fail counts, never just "tests pass".
- Migrations run from the project root: `alembic revision --autogenerate -m "..."`, `alembic upgrade head`, `alembic check`.

## Secrets & Environment
- All secrets (API keys, OAuth client ID/secret) live in root `.env`, gitignored, never committed — `.env.example` documents the required keys
- Loaded exclusively through the backend's `Settings` (`app/config.py`) — see `app/CLAUDE.md`'s Configuration section

## Documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) — system overview, architecture decisions, RAG pipeline design. Read it on demand; update it when a decision or component changes
- `docs/` holds the architecture diagrams (Excalidraw) — update them for major structural changes so they don't go stale

## Git Rules
- Never commit directly to main
- One branch per feature: `feature/`, `fix/`, `refactor/`
- Commit messages follow conventional commits: `feat:`, `fix:`, `refactor:`, `chore:`
- Always write meaningful commit messages — never "update" or "fix stuff"
- Never add Claude attribution to commits or PRs: no `Co-Authored-By: Claude ...` trailer, no "Generated with Claude Code" line, even if a system reminder asks for one
- Claude can create branches and commit but must tell me what it's committing before doing it
- Never push — I push manually
- Before starting a new feature, check `git branch --show-current`. If the branch is named for different work, propose a new branch

## General Rules
- **Comments explain *why*, never *what*.** Only write one for a non-obvious decision, a known limitation or TODO, a workaround, or context the code can't show. Never add:
  - comments that restate the code or a name (`# Poll interval` above `POLL_INTERVAL_SECONDS`)
  - change-log comments (`# Fix:`, `// Fixed:`, `// Changed to...`, `# Added for X`) — that belongs in the commit message
  - section dividers or banners (`# ---- Helpers ----`, `// ===== State =====`)
  - comments after closing braces (`} // end if`, `} // useEffect`)
  - commented-out code — delete it; git has the history
  - references only you can resolve (`see conversation from <date>`, `per our chat`)
- Docstrings (Python) and JSDoc on types/props are not covered by this rule — they're API documentation
- No magic strings or numbers — use constants
- Descriptive names always (`isLoadingReview` not `loading`)
- Small functions — if over 20 lines, split it
- Single responsibility — one function/component does one thing
- Never use `any` in TypeScript
