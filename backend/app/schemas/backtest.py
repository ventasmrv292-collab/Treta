"""Backtest schemas."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class BacktestRunCreate(BaseModel):
    strategy_family: str
    strategy_name: str
    strategy_version: str
    symbol: str = "BTCUSDT"
    interval: str = "15m"
    start_time: datetime
    end_time: datetime
    initial_capital: Decimal = Field(ge=0, decimal_places=2)
    leverage: int = Field(ge=1, le=125)
    fee_profile: str = "realistic"
    slippage_bps: float = 0.0
    params_json: str | None = None


class BacktestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    trade_index: int
    entry_time: datetime
    exit_time: datetime
    position_side: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    exit_reason: str


class BacktestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_family: str
    strategy_name: str
    strategy_version: str
    symbol: str
    interval: str
    start_time: datetime
    end_time: datetime
    initial_capital: Decimal
    leverage: int
    fee_profile: str
    slippage_bps: float
    params_json: str | None
    status: str
    total_trades: int | None
    net_pnl: Decimal | None
    gross_pnl: Decimal | None
    total_fees: Decimal | None
    win_rate: float | None
    profit_factor: float | None
    max_drawdown_pct: float | None
    created_at: datetime
    final_capital: Decimal | None = None
    peak_equity: Decimal | None = None
    min_equity: Decimal | None = None
    results: list[BacktestResultResponse] = []
