"""Trade model for simulated operations."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, DateTime, Text, Integer, BigInteger, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Paper account & signal (nullable for legacy trades)
    account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("paper_accounts.id"), nullable=True, index=True)
    signal_event_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("signal_events.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN", index=True)  # OPEN, CLOSED
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    margin_used_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    capital_before_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    capital_after_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    fee_config_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("fee_configs.id"), nullable=True)
    risk_profile_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("risk_profiles.id"), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Source & strategy
    source: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # manual, n8n
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)  # usdt_m, coin_m
    strategy_family: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"), nullable=True, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)

    # Position
    position_side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG, SHORT
    order_side_entry: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY, SELL
    order_type_entry: Mapped[str] = mapped_column(String(16), nullable=False)  # MARKET, LIMIT
    maker_taker_entry: Mapped[str | None] = mapped_column(String(8), nullable=True)  # MAKER, TAKER
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)  # 10, 20
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    # Entry
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    signal_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    strategy_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Régimen y trazabilidad de entrada (señal / pending / ejecución)
    market_regime_detected: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    regime_timeframe_used: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cooldown_active_at_open: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    market_regime_at_signal: Mapped[str | None] = mapped_column(String(48), nullable=True)
    regime_timeframe_at_signal: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cooldown_active_at_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regime_changed_since_pending: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    entry_source: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)  # IMMEDIATE | PENDING_FILL
    pending_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Exit (nullable until closed)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    exit_order_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    maker_taker_exit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Computed / stored for analytics
    entry_notional: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    exit_notional: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    entry_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    exit_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    funding_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    slippage_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    gross_pnl_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    net_pnl_usdt: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    pnl_pct_notional: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pnl_pct_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Ex-ante al abrir (FASE 1 net RR)
    expected_net_rr_at_open: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    estimated_total_cost_usdt_at_open: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    estimated_total_cost_pct_at_open: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    take_profit_base_at_open: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    strategy_rel: Mapped["Strategy | None"] = relationship("Strategy", back_populates="trades", lazy="selectin")

    __table_args__ = (Index("ix_trades_closed_at", "closed_at"), Index("ix_trades_created_at", "created_at"))
