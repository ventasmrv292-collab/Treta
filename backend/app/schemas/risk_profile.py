"""Risk profile schemas."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RiskProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sizing_mode: str
    fixed_quantity: Decimal | None = None
    fixed_notional_usdt: Decimal | None = None
    risk_pct_per_trade: Decimal | None = None
    max_open_positions: int
    max_margin_pct_of_account: Decimal
    max_daily_loss_usdt: Decimal | None = None
    max_daily_loss_pct: Decimal | None = None
    cooldown_after_losses: int | None = None
    allowed_leverage_json: str | None = None
    created_at: datetime
    updated_at: datetime


class PositionSizePreviewResponse(BaseModel):
    """Preview de quantity y margen según risk profile."""
    quantity: Decimal
    entry_notional: Decimal
    margin_used_usdt: Decimal
    entry_fee_estimate: Decimal
    estimated_loss_to_sl_usdt: Decimal | None  # si hay stop_loss
