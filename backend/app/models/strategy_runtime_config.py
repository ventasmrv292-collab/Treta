"""Runtime config per strategy/symbol/timeframe: allow_long, allow_short, active, max_open_positions, cooldown."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class StrategyRuntimeConfig(Base):
    __tablename__ = "strategy_runtime_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, default="BTCUSDT")
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    allow_long: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_short: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_win_rate_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_recent_drawdown_threshold: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    min_stop_distance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    min_rr_ratio: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    max_slippage_usdt_estimated: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_slippage_pct_of_notional: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
