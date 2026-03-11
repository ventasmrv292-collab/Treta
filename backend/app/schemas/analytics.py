"""Analytics and dashboard schemas."""
from decimal import Decimal
from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: Decimal
    net_pnl: Decimal
    total_fees: Decimal
    profit_factor: float
    pnl_by_strategy: list[dict]
    pnl_by_leverage: list[dict]


class StrategyComparison(BaseModel):
    strategy_name: str
    strategy_family: str
    strategy_version: str | None = None
    total_trades: int
    net_pnl: Decimal
    gross_pnl: Decimal
    total_fees: Decimal
    win_rate: float
    profit_factor: float
    avg_win: Decimal
    avg_loss: Decimal
    expectancy: Decimal


class StrategyVersionComparison(BaseModel):
    """Comparativa v1 vs v2: por strategy_name, strategy_version, timeframe, side; incluye slippage."""
    strategy_family: str
    strategy_name: str
    strategy_version: str
    timeframe: str
    position_side: str
    total_trades: int
    closed_trades: int
    gross_pnl: Decimal
    net_pnl: Decimal
    total_fees: Decimal
    total_slippage_usdt: Decimal
    avg_slippage_usdt: Decimal
    win_rate: float
    avg_win: Decimal
    avg_loss: Decimal
    profit_factor: float


class LeverageComparison(BaseModel):
    leverage: int
    total_trades: int
    net_pnl: Decimal
    win_rate: float
    total_fees: Decimal
