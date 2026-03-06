"""Backtest equity curve point."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, DateTime, BigInteger, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BacktestEquityCurve(Base):
    __tablename__ = "backtest_equity_curve"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    point_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    equity_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    used_margin_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
