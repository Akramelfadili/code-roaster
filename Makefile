.PHONY: help run run-back run-front \
        lint-back format-back type-back security-back test-back \
        lint-front format-front type-front test-front \
        check-all

# ── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Dev ──────────────────────────────────────────────────────────────────────

run: ## Run backend and frontend together (honcho)
	honcho start

# ── Backend ──────────────────────────────────────────────────────────────────

run-back: ## Run the FastAPI backend with auto-reload
	uvicorn app.main:app --reload

lint-back: ## Ruff lint check on app/
	ruff check app/

format-back: ## Ruff format app/ (mutates files)
	ruff format app/

type-back: ## Mypy strict type check on app/
	mypy app/

security-back: ## Bandit security scan on app/
	bandit -r app/ -c .bandit --exclude app/tests

test-back: ## Pytest suite in app/tests/
	cd app && pytest

# ── Frontend ─────────────────────────────────────────────────────────────────

run-front: ## Run the Vite dev server
	cd frontend && npm run dev

lint-front: ## Oxlint on frontend/src/
	cd frontend && npm run lint

format-front: ## Prettier format check on frontend/src/
	cd frontend && npx prettier --check src/

type-front: ## TypeScript type check (tsc --noEmit)
	cd frontend && npx tsc --noEmit

test-front: ## Vitest suite in frontend/
	cd frontend && npm run test

# ── Combined ─────────────────────────────────────────────────────────────────

check-all: lint-back type-back security-back lint-front format-front type-front ## Run all checks (no format-back — it mutates)
