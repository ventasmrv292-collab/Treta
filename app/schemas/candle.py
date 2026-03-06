"""Candle schemas."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class CandleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    interval: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    created_at: datetime


class CandleListResponse(BaseModel):
    items: list[CandleResponse]
    total: int
