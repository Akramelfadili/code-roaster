"""Async SQLAlchemy engine, session factory, declarative base and schema setup.

Postgres is the single home of persisted state (indexing and review jobs
today, agent runs next) — nothing that must survive a restart or be shared between
workers lives in process memory. The `lifespan` in `main.py` calls
`init_db` once at startup to run the Alembic migrations, and puts
`SessionFactory` on `app.state`, where `get_db` and the background job
runners read it.
"""

from collections.abc import AsyncIterator
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends, Request
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
_ALEMBIC_HEAD = "head"

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base every ORM table in `app/models/db/` inherits from."""


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Store a `StrEnum`'s lowercase values in Postgres, not its member names."""
    return [member.value for member in enum_class]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session for one request, closed once the request is done."""
    session_factory: async_sessionmaker[AsyncSession] = (
        request.app.state.session_factory
    )
    async with session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]

# Closed as soon as the path operation function returns, instead of after the
# response is sent. SSE routes use it, so a stream that stays open for minutes
# doesn't hold a pooled connection; the stream itself opens short sessions.
FunctionScopedDbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]


async def init_db() -> None:
    """Bring the schema up to date by running every pending Alembic migration.

    Runs in every environment, so the schema is always exactly what the
    migrations define — never a `create_all` shortcut that can drift.
    """
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade_to_head)


def _upgrade_to_head(connection: Connection) -> None:
    """Run every pending Alembic migration on `connection`.

    `app/migrations/env.py` picks the connection up from `config.attributes`
    instead of opening its own, since it is called from a running event loop.
    """
    config = Config(_ALEMBIC_INI)
    config.attributes["connection"] = connection
    command.upgrade(config, _ALEMBIC_HEAD)
