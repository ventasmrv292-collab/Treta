"""Fee configuration model for simulation."""
from datetime import datetime
from sqlalchemy import String, Numeric, Boolean, DateTime, func, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class FeeConfig(Base):
    __tablename__ = "fee_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # conservative, realistic, optimistic
    maker_fee_bps: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)  # basis points
    taker_fee_bps: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    bnb_discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)  # 0-100
    default_slippage_bps: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    include_funding: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
