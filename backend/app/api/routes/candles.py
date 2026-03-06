"""Candles API - historical klines from DB or Binance."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from datetime import datetime

from app.db import get_db
from app.models.candle import Candle
from app.schemas.candle import CandleResponse, CandleListResponse
from app.services.market_data import MarketDataService

router = APIRouter()


@router.get("", response_model=CandleListResponse)
async def get_candles(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("15m"),
    limit: int = Query(500, le=1500),
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    db=Depends(get_db),
):
    """Get candles: from DB if stored, else fetch from Binance and return (optionally persist)."""
    svc = MarketDataService()
    start_ts = int(from_time.timestamp() * 1000) if from_time else None
    end_ts = int(to_time.timestamp() * 1000) if to_time else None
    klines = await svc.get_klines(symbol=symbol, interval=interval, limit=limit, start_time=start_ts, end_time=end_ts)

    # Map to response format (no DB persist by default to keep endpoint simple)
    items = [
        CandleResponse(
            id=0,
            symbol=symbol,
            interval=interval,
            open_time=k["open_time"],
            open=k["open"],
            high=k["high"],
            low=k["low"],
            close=k["close"],
            volume=k["volume"],
            created_at=k["open_time"],
        )
        for k in klines
    ]
    return CandleListResponse(items=items, total=len(items))
