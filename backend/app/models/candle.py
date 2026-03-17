"""OHLCV candle model for backtesting and chart data."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Integer, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Candle(Base):
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    interval: Mapped[str] = mapped_column(String(8), index=True, nullable=False)  # 1m, 5m, 15m, 1h
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_closed: Mapped[bool] = mapped_column(default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="BINANCE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_candles_symbol_interval_time", "symbol", "interval", "open_time", unique=True),
    )
