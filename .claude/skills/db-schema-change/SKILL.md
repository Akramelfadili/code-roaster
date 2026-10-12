---
name: db-schema-change
description: Add or change a Postgres table, column, index or enum (SQLAlchemy models in app/models/db/) and its Alembic migration. Use for any change under app/models/db/ or app/migrations/.
---

# Database schema change

Rules: `app/CLAUDE.md` → *Database*. Rationale: ARCHITECTURE.md §3.8.

## Preconditions
- `.env` must define `DATABASE_URL` (and `TEST_DATABASE_URL` for tests), and Postgres must be up (`pg_isready -h localhost`). If either is missing, stop and tell the user. Don't work around it.

## Steps
1. Edit the model in `app/models/db/`. A new table module must be imported in `app/models/db/__init__.py`.
2. Conventions: `StrEnum` stored via `Enum(..., values_callable=enum_values)`. Use `native_enum=False` only for growing sets like `ReviewEventType`. Timestamps are `DateTime(timezone=True)`. Enforce invariants with constraints or partial unique indexes, never check-then-write.
3. From the project root: `alembic revision --autogenerate -m "<what changed>"`.
4. Review the generated file in `app/migrations/versions/`:
   - Autogenerate misses enum value changes and some partial indexes. Add them by hand.
   - Write literals only. Never import `app.constants` (migrations are frozen snapshots).
   - Make sure `downgrade()` actually reverses `upgrade()`.
5. Round-trip: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` → `alembic check` (must report no drift).
6. Services map rows to Pydantic models. Routes never return ORM objects, and DB access stays in `app/services/`. Translate actionable DB errors to domain exceptions (pattern: `IntegrityError` → `IndexingAlreadyInProgressError`).
7. A new job type needs an orphan sweep wired in the lifespan (see `fail_orphaned_review_jobs`).
8. Tests use the `db_session_factory` fixture. Without `TEST_DATABASE_URL` they are skipped, so report the skip count, not "all passed".
9. Update the table and column descriptions in ARCHITECTURE.md §3.8/§3.9.
