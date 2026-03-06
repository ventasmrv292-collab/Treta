"""Bot log model for audit and operational events."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, DateTime, BigInteger, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BotLog(Base):
    __tablename__ = "bot_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_trade_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_signal_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
