# Code Roaster — CLAUDE.md (Global)

## Project Overview
AI-powered code review tool. Users either paste code directly or connect their GitHub account and submit a pull request URL — either way, they get a structured review with bugs, security issues, suggestions, and a score. Built by a full stack dev learning AI engineering.

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
- Claude can create branches and commit but must tell me what it's committing before doing it
- Never push — I push manually

## General Rules
- No commented out code
- No magic strings or numbers — use constants
- Descriptive names always (`isLoadingReview` not `loading`)
- Small functions — if over 20 lines, split it
- Single responsibility — one function/component does one thing
- Never use `any` in TypeScript
