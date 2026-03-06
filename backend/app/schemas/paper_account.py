"""Paper account schemas."""
from decimal import Decimal
from pydantic import BaseModel


class PaperAccountResponse(BaseModel):
    id: int
    name: str
    base_currency: str
    initial_balance_usdt: Decimal
    current_balance_usdt: Decimal
    available_balance_usdt: Decimal
    used_margin_usdt: Decimal
    realized_pnl_usdt: Decimal
    unrealized_pnl_usdt: Decimal
    total_fees_usdt: Decimal
    status: str

    class Config:
        from_attributes = True


class DashboardSummaryResponse(BaseModel):
    """Resumen para dashboard: precio BTC, métricas de trades y cuenta paper."""
    # Precio (opcional, puede venir del market service)
    btc_price: str | None = None
    # Métricas existentes
    total_trades: int = 0
    win_rate: float = 0.0
    net_pnl: str = "0"
    gross_pnl: str = "0"
    total_fees: str = "0"
    profit_factor: float = 0.0
    pnl_by_strategy: list[dict] = []
    pnl_by_leverage: list[dict] = []
    # Cuenta paper (si account_id proporcionado)
    account: PaperAccountResponse | None = None
    equity_usdt: str | None = None  # current_balance + unrealized
    open_positions_count: int = 0  # operaciones abiertas de la cuenta
