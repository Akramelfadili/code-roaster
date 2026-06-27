.PHONY: lint-back format-back type-back security-back test-back \
        lint-front format-front type-front test-front \
        check-all

# ── Backend ──────────────────────────────────────────────────────────────────

lint-back:
	ruff check app/

format-back:
	ruff format app/

type-back:
	mypy app/

security-back:
	bandit -r app/ -c .bandit --exclude app/tests

test-back:
	cd app && pytest

# ── Frontend ─────────────────────────────────────────────────────────────────

lint-front:
	cd frontend && npm run lint

format-front:
	cd frontend && npx prettier --check src/

type-front:
	cd frontend && npx tsc --noEmit

test-front:
	cd frontend && npm run test

# ── Combined ─────────────────────────────────────────────────────────────────

check-all: lint-back type-back security-back lint-front format-front type-front
