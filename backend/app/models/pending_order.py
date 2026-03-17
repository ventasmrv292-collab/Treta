"""Orden pendiente: LIMIT o STOP creada desde una señal; se ejecuta cuando el precio toca el nivel o expira."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, Integer, DateTime, Text, BigInteger, ForeignKey, func  # BigInteger for signal_event_id
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PendingOrder(Base):
    """
    Orden pendiente separada del trade ejecutado.
    Estados: PENDING, FILLED, EXPIRED, CANCELLED.
    """
    __tablename__ = "pending_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("signal_events.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True, index=True)

    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("paper_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    risk_profile_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("risk_profiles.id", ondelete="SET NULL"), nullable=True)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    position_side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG, SHORT
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # LIMIT, STOP

    # Precio al que se activa la orden (trigger)
    trigger_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    strategy_family: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)  # PENDING, FILLED, EXPIRED, CANCELLED
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_after_bars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
