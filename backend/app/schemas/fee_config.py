"""Fee config schemas."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class FeeConfigBase(BaseModel):
    name: str
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    bnb_discount_pct: Decimal = Decimal("0")
    default_slippage_bps: Decimal = Decimal("0")
    include_funding: bool = True
    is_default: bool = False


class FeeConfigUpdate(BaseModel):
    maker_fee_bps: Decimal | None = None
    taker_fee_bps: Decimal | None = None
    bnb_discount_pct: Decimal | None = None
    default_slippage_bps: Decimal | None = None
    include_funding: bool | None = None
    is_default: bool | None = None


class FeeConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    bnb_discount_pct: Decimal
    default_slippage_bps: Decimal
    include_funding: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
