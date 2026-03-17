"""Risk profile model for position sizing and limits."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, BigInteger, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sizing_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    fixed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    fixed_notional_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    risk_pct_per_trade: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_margin_pct_of_account: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=100)
    max_daily_loss_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    max_daily_loss_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    cooldown_after_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_leverage_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
