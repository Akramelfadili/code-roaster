from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.exceptions import BudgetExceededError
from app.models.db import DailySpend
from app.services.cost_budget import CostBudget

_DAILY_LIMIT_USD = 1.0


async def _spent_today(session_factory: async_sessionmaker[AsyncSession]) -> Decimal:
    async with session_factory() as session:
        spent = await session.scalar(
            select(DailySpend.spent_usd).where(
                DailySpend.day == datetime.now(UTC).date()
            )
        )
    assert spent is not None
    return spent


class TestCostBudget:
    async def test_no_spend_yet_allows_calls(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        budget = CostBudget(db_session_factory, _DAILY_LIMIT_USD)

        await budget.ensure_available()

    async def test_record_accumulates_todays_spend(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        budget = CostBudget(db_session_factory, _DAILY_LIMIT_USD)

        await budget.record(0.25)
        await budget.record(0.125)

        assert await _spent_today(db_session_factory) == Decimal("0.375")

    async def test_spend_below_limit_allows_calls(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        budget = CostBudget(db_session_factory, _DAILY_LIMIT_USD)
        await budget.record(0.99)

        await budget.ensure_available()

    async def test_spend_at_limit_raises_budget_exceeded(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        budget = CostBudget(db_session_factory, _DAILY_LIMIT_USD)
        await budget.record(_DAILY_LIMIT_USD)

        with pytest.raises(BudgetExceededError):
            await budget.ensure_available()

    async def test_previous_days_spend_does_not_count_today(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        async with db_session_factory() as session:
            session.add(DailySpend(day=yesterday, spent_usd=Decimal("5")))
            await session.commit()
        budget = CostBudget(db_session_factory, _DAILY_LIMIT_USD)

        await budget.ensure_available()
