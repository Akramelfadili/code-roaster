# Code Roaster — CLAUDE.md (Global)

## Project Overview
AI-powered code review tool. Users paste code → get structured review with bugs, security issues, suggestions, and a score. Built by a full stack dev learning AI engineering.

## Tech Stack
- **Backend:** Python, FastAPI, Anthropic SDK (Claude Sonnet)
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, React Query
- **AI:** Claude API (streaming + function calling)
- **Package manager:** conda (backend), npm (frontend)

## Project Structure
```
code-roaster/
├── app/                  # FastAPI backend
│   ├── models/           # Pydantic request/response models
│   │   └── review.py
│   ├── prompts/          # AI prompt strings and tool definitions
│   │   └── review.py
│   ├── routes/           # API route handlers
│   ├── tests/            # Backend tests
│   │   ├── conftest.py   # Pytest fixtures
│   │   ├── mocks.py      # Shared mock data
│   │   └── test_routes.py
│   ├── main.py           # FastAPI entry point (run: uvicorn app.main:app)
│   ├── reviewer.py       # AI reviewer logic
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pytest.ini
├── frontend/             # React frontend
│   └── src/
│       ├── api/          # API calls
│       ├── hooks/        # Custom React hooks
│       ├── components/   # UI components
│       ├── types/        # TypeScript types/interfaces/enums
│       ├── utils/        # Helper functions
│       └── constants/    # Constants and magic values
└── README.md
```

## Commands

All commands run from the project root via `make`.

| Command | What it does |
|---|---|
| `make lint-back` | Ruff lint check on `app/` |
| `make format-back` | Ruff format `app/` (mutates files) |
| `make type-back` | Mypy strict type check on `app/` |
| `make security-back` | Bandit security scan on `app/` |
| `make test-back` | Pytest suite in `app/tests/` |
| `make lint-front` | Oxlint on `frontend/src/` |
| `make format-front` | Prettier format check on `frontend/src/` |
| `make type-front` | TypeScript type check (`tsc --noEmit`) |
| `make test-front` | Vitest suite in `frontend/` |
| `make check-all` | Runs all checks (no format-back — it mutates) |

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
