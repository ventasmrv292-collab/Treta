"""Trade schemas."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class TradeBase(BaseModel):
    symbol: str
    market: str = "usdt_m"
    strategy_family: str
    strategy_name: str
    strategy_version: str
    timeframe: str
    position_side: str  # LONG, SHORT
    leverage: int = Field(ge=1, le=125)
    quantity: Decimal
    entry_price: Decimal
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    notes: str | None = None


class ManualTradeCreate(TradeBase):
    source: str = "manual"
    order_side_entry: str  # BUY, SELL
    order_type_entry: str = "MARKET"  # MARKET, LIMIT
    maker_taker_entry: str = "TAKER"  # MAKER, TAKER
    account_id: int | None = None
    fee_config_id: int | None = None
    risk_profile_id: int | None = None


class ManualTradeClose(BaseModel):
    exit_price: Decimal
    exit_order_type: str = "MARKET"
    maker_taker_exit: str = "TAKER"
    exit_reason: str
    closed_at: datetime | None = None

    @field_validator("exit_price", mode="before")
    @classmethod
    def normalize_exit_price(cls, v):
        if isinstance(v, str):
            return v.replace(",", "").strip() or "0"
        return v


class N8nTradeCreate(BaseModel):
    source: str = "n8n"
    strategy_id: int | None = None
    symbol: str
    market: str = "usdt_m"
    strategy_family: str
    strategy_name: str
    strategy_version: str
    timeframe: str
    position_side: str
    leverage: int = Field(ge=1, le=125)
    entry_price: Decimal
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    quantity: Decimal
    entry_order_type: str = "MARKET"
    maker_taker_entry: str = "TAKER"
    signal_timestamp: datetime | None = None
    strategy_params_json: str | None = None
    notes: str | None = None
    account_id: int | None = None
    risk_profile_id: int | None = None
    idempotency_key: str | None = None


class TradeCreate(BaseModel):
    """Generic create - backend can set source."""
    pass


class TradeUpdate(BaseModel):
    exit_price: Decimal | None = None
    exit_order_type: str | None = None
    maker_taker_exit: str | None = None
    exit_reason: str | None = None
    closed_at: datetime | None = None
    notes: str | None = None


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None = None
    signal_event_id: int | None = None
    status: str | None = None
    opened_at: datetime | None = None
    margin_used_usdt: Decimal | None = None
    capital_before_usdt: Decimal | None = None
    capital_after_usdt: Decimal | None = None
    risk_profile_id: int | None = None
    source: str
    symbol: str
    market: str
    strategy_family: str
    strategy_name: str
    strategy_version: str
    timeframe: str
    position_side: str
    order_side_entry: str
    order_type_entry: str
    maker_taker_entry: str | None
    leverage: int
    quantity: Decimal
    entry_price: Decimal
    take_profit: Decimal | None
    stop_loss: Decimal | None
    signal_timestamp: datetime | None
    strategy_params_json: str | None
    notes: str | None
    exit_price: Decimal | None
    exit_order_type: str | None
    maker_taker_exit: str | None
    exit_reason: str | None
    closed_at: datetime | None
    entry_notional: Decimal | None
    exit_notional: Decimal | None
    entry_fee: Decimal | None
    exit_fee: Decimal | None
    funding_fee: Decimal | None
    slippage_usdt: Decimal | None
    gross_pnl_usdt: Decimal | None
    net_pnl_usdt: Decimal | None
    pnl_pct_notional: Decimal | None
    pnl_pct_margin: Decimal | None
    created_at: datetime
    updated_at: datetime
    # Estado de la señal asociada (si existe): RECEIVED, ACCEPTED, PENDING_ORDER, STALE, EXPIRED, REJECTED
    signal_event_status: str | None = None
    market_regime_detected: str | None = None
    regime_timeframe_used: str | None = None
    cooldown_active_at_open: bool | None = None
    market_regime_at_signal: str | None = None
    regime_timeframe_at_signal: str | None = None
    cooldown_active_at_signal: bool | None = None
    regime_changed_since_pending: bool | None = None
    entry_source: str | None = None
    pending_order_id: int | None = None


class TradeListResponse(BaseModel):
    items: list[TradeResponse]
    total: int
    page: int
    size: int
    pages: int
