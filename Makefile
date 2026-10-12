.PHONY: help run run-back run-front \
        lint-back format-back type-back security-back test-back \
        lint-front format-front type-front test-front \
        check-all \
        db-up db-down db-reset db-test-up db-migrate db-shell dev

# ── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

DB_SERVICE      := postgres
DB_TEST_SERVICE := postgres-test
DB_USER         := postgres
DB_NAME         := code_roaster

# ── Dev ──────────────────────────────────────────────────────────────────────

run: ## Run backend and frontend together (honcho)
	honcho start

dev: ## Start Postgres, then the backend with auto-reload
	docker compose up -d --wait $(DB_SERVICE) && uvicorn app.main:app --reload

# ── Database (Docker Compose) ────────────────────────────────────────────────

db-up: ## Start the dev Postgres in the background (port 5432)
	docker compose up -d --wait $(DB_SERVICE)

db-down: ## Stop all compose containers (dev data is kept in the volume)
	docker compose down

db-reset: ## Wipe the dev Postgres volume and start it fresh
	docker compose down -v && docker compose up -d --wait $(DB_SERVICE)

db-test-up: ## Start the ephemeral test Postgres (port 5433)
	docker compose up -d --wait $(DB_TEST_SERVICE)

db-migrate: ## Run alembic upgrade head (needs db-up first)
	alembic upgrade head

db-shell: ## Open psql in the running dev Postgres container
	docker compose exec $(DB_SERVICE) psql -U $(DB_USER) -d $(DB_NAME)

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
	cd app && pytest -vv

# ── Frontend ─────────────────────────────────────────────────────────────────

run-front: ## Run the Vite dev server
	cd frontend && npm run dev

lint-front: ## ESLint on frontend/src/
	cd frontend && npm run lint

format-front: ## Prettier format check on frontend/src/
	cd frontend && npx prettier --check src/

type-front: ## TypeScript type check (tsc -b tsconfig.app.json --noEmit)
	cd frontend && npx tsc -b tsconfig.app.json --noEmit

test-front: ## Vitest suite in frontend/
	cd frontend && npm run test

# ── Combined ─────────────────────────────────────────────────────────────────

check-all: lint-back type-back security-back test-back lint-front format-front type-front test-front ## Run all checks (no format-back — it mutates)
