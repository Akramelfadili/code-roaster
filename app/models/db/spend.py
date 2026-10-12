"""The `daily_spend` table — the running AI spend per UTC day."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_SPEND_PRECISION = 12
_SPEND_SCALE = 6


class DailySpend(Base):
    """Approximate USD spent on Claude and Voyage AI calls during one UTC day.

    One row per day, shared by every worker. `CostBudget` checks it before
    each call and adds the call's cost after it, with an atomic upsert so
    concurrent calls never lose an increment.
    """

    __tablename__ = "daily_spend"

    day: Mapped[date] = mapped_column(primary_key=True)
    spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(_SPEND_PRECISION, _SPEND_SCALE), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
