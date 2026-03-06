"""Account ledger model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, BigInteger, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountLedger(Base):
    __tablename__ = "account_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True, index=True)
    backtest_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("backtest_runs.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    balance_before_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    balance_after_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
