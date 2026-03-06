"""Backtest run and result models."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Integer, Text, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_family: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    slippage_bps: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("strategies.id"), nullable=True)
    fee_config_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("fee_configs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)  # pending, running, completed, failed
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_capital: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    peak_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    min_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_funding: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_slippage: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    used_margin_peak: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    net_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    gross_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_fees: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results: Mapped[list["BacktestResult"]] = relationship("BacktestResult", back_populates="run", cascade="all, delete-orphan")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), nullable=False, index=True)
    trade_index: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    position_side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(64), nullable=False)

    run: Mapped["BacktestRun"] = relationship("BacktestRun", back_populates="results")
