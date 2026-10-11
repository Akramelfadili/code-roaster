"""Alembic environment — runs migrations against `Settings.database_url`.

Two ways in:
- **CLI** (`alembic upgrade head` from the project root): opens its own async
  engine and runs the migrations through it.
- **App startup** (`init_db` in production): `app/database.py` passes its
  open connection in `config.attributes["connection"]`, because the CLI path's
  `asyncio.run` can't be called from the already running event loop.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.models.db  # noqa: F401 — registers every table on Base.metadata
from app.config import settings
from app.database import Base

config = context.config
target_metadata = Base.metadata


def _run_migrations(connection: Connection) -> None:
    """Run the pending migrations on an open connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_with_own_engine() -> None:
    """Open a short-lived engine for a CLI run and migrate through it."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


def _run_migrations_offline() -> None:
    """Emit the migration SQL as a script (`alembic upgrade head --sql`)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


shared_connection: Connection | None = config.attributes.get("connection")

if context.is_offline_mode():
    _run_migrations_offline()
elif shared_connection is not None:
    _run_migrations(shared_connection)
else:
    # Only configure logging for CLI runs — at app startup it would replace
    # the logging set up in main.py.
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    asyncio.run(_run_migrations_with_own_engine())
