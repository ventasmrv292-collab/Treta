"""Signal event model (n8n / external signals)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, BigInteger, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SignalEvent(Base):
    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy_family: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RECEIVED")
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
