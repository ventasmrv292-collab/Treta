"""Paper account model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USDT")
    initial_balance_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    current_balance_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    available_balance_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    used_margin_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    realized_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    unrealized_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_fees_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationships (optional, for ORM access)
    # trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="account", foreign_keys="Trade.account_id")
