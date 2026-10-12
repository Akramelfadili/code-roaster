"""Enforce the daily AI cost budget across every worker.

Every Claude and Voyage AI call goes through `CostBudget`: `ensure_available`
before the call, `record` with its approximate cost after it. The running
total lives in the `daily_spend` table, never in process memory, so every
worker enforces the same budget and it survives restarts.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.exceptions import BudgetExceededError
from app.models.db import DailySpend


def _today_utc() -> date:
    return datetime.now(UTC).date()


class CostBudget:
    """Checks and records approximate AI spend against a daily USD limit."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        daily_limit_usd: float,
    ) -> None:
        """Wire the budget to the database and its limit.

        Args:
            session_factory: Opens a short session per check and per record.
            daily_limit_usd: Spend per UTC day at which calls start failing
                (`settings.daily_cost_budget_usd`).
        """
        self._session_factory = session_factory
        self._daily_limit_usd = Decimal(str(daily_limit_usd))

    async def ensure_available(self) -> None:
        """Fail before a call once today's spend has reached the limit.

        The cost of a call is only known after it, so this is a soft limit:
        calls already in flight when the limit is reached can push spend a
        little past it.

        Raises:
            BudgetExceededError: Today's spend is at or over the limit.
        """
        async with self._session_factory() as session:
            spent_usd = await session.scalar(
                select(DailySpend.spent_usd).where(DailySpend.day == _today_utc())
            )
        if spent_usd is not None and spent_usd >= self._daily_limit_usd:
            raise BudgetExceededError(
                f"Daily cost budget of ${self._daily_limit_usd} reached "
                f"(spent ${spent_usd})"
            )

    async def record(self, cost_usd: float) -> None:
        """Add one call's approximate cost to today's spend."""
        cost = Decimal(str(cost_usd))
        statement = insert(DailySpend).values(day=_today_utc(), spent_usd=cost)
        # An upsert, so concurrent calls on any worker each add their cost
        # instead of overwriting each other's read-modify-write.
        statement = statement.on_conflict_do_update(
            index_elements=[DailySpend.day],
            set_={"spent_usd": DailySpend.spent_usd + statement.excluded.spent_usd},
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()
