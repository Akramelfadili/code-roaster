# Code Roaster

> AI-powered code review in seconds. Paste your code, get a structured critique — bugs, security issues, suggestions, and a quality score — powered by Claude.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![Node](https://img.shields.io/badge/Node.js-24.x-339933?style=flat&logo=node.js&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)

---

## What It Does

Paste any code snippet, pick a language, and Code Roaster sends it to Claude for a thorough review. You get back:

- **A quality score** (0–100) with an overall severity rating
- **Bugs** — logic errors, edge cases, incorrect assumptions
- **Security issues** — common vulnerabilities and risky patterns
- **Suggestions** — performance, readability, and best-practice improvements
- **Positives** — what the code already does well

Reviews stream in real time so you're not staring at a blank screen.

---

## Tech Stack

### Backend

| Tool | Version | Role |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | ≥ 0.115 | API framework |
| Anthropic SDK | ≥ 0.40 | Claude API client |
| Pydantic v2 | bundled with FastAPI | Request/response validation |
| Uvicorn | ≥ 0.32 | ASGI server |
| conda | latest | Environment management |

### Frontend

| Tool | Version | Role |
|---|---|---|
| React | 19 | UI framework |
| TypeScript | 6 | Type safety |
| Vite | 8 | Build tool & dev server |
| Tailwind CSS | v4 | Styling |
| TanStack Query | v5 | Async state management |
| Vitest | latest | Unit / component tests |
| Testing Library | latest | DOM testing utilities |

### AI

| Tool | Detail |
|---|---|
| Model | `claude-sonnet-4-6` |
| Structured output | Tool use / function calling |
| Streaming | Server-Sent Events via `StreamingResponse` |
| Prompt caching | `cache_control: ephemeral` on system prompts |

---

## Project Structure

```
code-roaster/
├── app/                        # FastAPI backend
│   ├── models/
│   │   └── review.py           # Pydantic request & response models
│   ├── prompts/
│   │   └── review.py           # System prompts and tool definitions
│   ├── routes/
│   │   └── review.py           # Route handlers (/review, /review/stream, /review/structured)
│   ├── tests/
│   │   ├── conftest.py         # Shared pytest fixtures
│   │   ├── mocks.py            # Shared mock data
│   │   └── test_routes.py      # Route-level integration tests
│   ├── main.py                 # FastAPI app setup and lifespan
│   ├── reviewer.py             # CodeReviewer class — all AI logic
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pytest.ini
├── frontend/
│   └── src/
│       ├── api/                # Typed API call functions
│       ├── components/         # UI components
│       ├── constants/          # Magic values and enums
│       ├── hooks/              # Custom React hooks
│       ├── tests/              # Component & integration tests
│       ├── types/              # TypeScript interfaces
│       └── utils/              # Helper functions
├── .bandit                     # Bandit security scanner config
├── .pre-commit-config.yaml     # Pre-commit hook definitions
├── Makefile                    # All dev commands
├── mypy.ini                    # Mypy strict config
└── ruff.toml                   # Ruff lint & format config
```

---

## Getting Started

### Prerequisites

- [conda](https://docs.conda.io/en/latest/miniconda.html) (or mamba)
- [Node.js](https://nodejs.org/) ≥ 20.x
- An [Anthropic API key](https://console.anthropic.com/)

### 1 — Clone

```bash
git clone https://github.com/your-username/code-roaster.git
cd code-roaster
```

### 2 — Backend setup

```bash
# Create and activate the conda environment
conda create -n code-roaster python=3.12
conda activate code-roaster

# Install runtime dependencies
pip install -r app/requirements.txt

# Install dev dependencies (tests, linting, type checking)
pip install -r app/requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 3 — Frontend setup

```bash
cd frontend
npm install
cd ..
```

### 4 — Environment variables

Create a `.env` file in the project root:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

The backend loads this automatically via `python-dotenv` on startup.

### 5 — Run

Open two terminals:

**Terminal 1 — Backend**
```bash
conda activate code-roaster
uvicorn app.main:app --reload
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
# App available at http://localhost:5173
```

---

## Make Commands

All commands run from the project root.

### Backend

| Command | What it does |
|---|---|
| `make lint-back` | Ruff lint check on `app/` |
| `make format-back` | Ruff format `app/` (mutates files) |
| `make type-back` | Mypy strict type check |
| `make security-back` | Bandit security scan (excludes tests) |
| `make test-back` | Pytest suite |

### Frontend

| Command | What it does |
|---|---|
| `make lint-front` | ESLint via oxlint on `frontend/src/` |
| `make format-front` | Prettier format check on `frontend/src/` |
| `make type-front` | TypeScript type check (`tsc --noEmit`) |
| `make test-front` | Vitest suite |

### Combined

| Command | What it does |
|---|---|
| `make check-all` | Lint + types + security across both stacks (no format-back — it mutates) |

---

## Running Tests

### Backend

```bash
conda activate code-roaster
make test-back
```

Tests live in `app/tests/`. The suite uses `pytest-asyncio` with `asyncio_mode = auto` — no `@pytest.mark.asyncio` decorators needed. The Anthropic client is mocked in all tests; no real API calls are made.

### Frontend

```bash
make test-front
```

Tests use Vitest + Testing Library with `happy-dom`. Component tests live in `frontend/src/tests/`.

---

## Pre-commit Hooks

Pre-commit runs automatically on every `git commit` against staged files. The hook chain is:

| Hook | Tool | What it catches |
|---|---|---|
| `trailing-whitespace` | pre-commit-hooks | Trailing spaces |
| `end-of-file-fixer` | pre-commit-hooks | Missing newlines |
| `ruff` | Ruff | Lint errors — auto-fixes imports and style |
| `ruff-format` | Ruff | Formatting |
| `mypy` | Mypy | Type errors (strict mode) |
| `bandit` | Bandit | Security vulnerabilities in Python |
| `frontend-eslint` | ESLint | TypeScript/React lint errors |
| `frontend-prettier` | Prettier | Frontend formatting |

Run all hooks manually against every file:

```bash
pre-commit run --all-files
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/review` | One-shot review, returns full text |
| `POST` | `/review/stream` | Streaming review (SSE) |
| `POST` | `/review/structured` | Structured review via function calling |
| `GET` | `/health` | Health check |

All review endpoints accept:

```json
{
  "code": "string",
  "language": "python"
}
```

---

## Roadmap

### V1 — Foundation ✅
- FastAPI backend with `/review` endpoint
- Claude integration via Anthropic SDK with prompt caching
- Basic text review response
- Conda environment and project structure

### V2 — Structured Reviews + Frontend ✅
- Streaming review endpoint (`/review/stream`)
- Structured review via Claude function calling (`/review/structured`)
- React + TypeScript frontend with Tailwind CSS
- Score display, severity badge, and categorised findings
- Full quality toolchain: Ruff, Mypy, Bandit, ESLint, Prettier, pre-commit
- Pytest + Vitest test suites

### V3 — Polish + UX (planned)
- Syntax-highlighted code editor
- Language auto-detection
- Review history stored in `localStorage`
- Copy-to-clipboard for individual findings
- Keyboard shortcuts

### V4 — Persistence + Accounts (planned)
- User authentication (OAuth)
- Saved review history with search
- Shareable review links
- Usage dashboard and token cost tracking

### V5 — Integrations (planned)
- GitHub App for automatic PR reviews
- VS Code extension
- CLI tool (`roast <file>`)
- Diff-aware reviews (only review what changed)

---

## License

MIT — see [LICENSE](LICENSE).
