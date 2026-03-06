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
    total_trades: int
    net_pnl: Decimal
    gross_pnl: Decimal
    total_fees: Decimal
    win_rate: float
    profit_factor: float
    avg_win: Decimal
    avg_loss: Decimal
    expectancy: Decimal


class LeverageComparison(BaseModel):
    leverage: int
    total_trades: int
    net_pnl: Decimal
    win_rate: float
    total_fees: Decimal
