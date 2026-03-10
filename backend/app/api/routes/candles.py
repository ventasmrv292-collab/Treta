"""Candles API - historical klines from DB or Binance; control de calidad."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.candle import Candle
from app.schemas.candle import CandleResponse, CandleListResponse
from app.services.market_data import MarketDataService

router = APIRouter()


def _default_quality_response(symbol: str | None, interval: str | None) -> dict:
    return {
        "total_rows": 0,
        "invalid_volume": 0,
        "invalid_ohlc": 0,
        "open_after_close": 0,
        "invalid_interval": 0,
        "zero_volume": 0,
        "interval_mismatch": 0,
        "duplicates": 0,
        "temporal_gaps": 0,
        "filter_symbol": symbol or "",
        "filter_interval": interval or "",
    }


@router.get("/quality")
async def get_candles_quality(
    symbol: str | None = Query(None, description="Filtrar por símbolo (ej. BTCUSDT)"),
    interval: str | None = Query(None, description="Filtrar por intervalo (1m, 5m, 15m)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Reporte de calidad de la tabla candles (requiere función get_candles_quality_report en DB).
    Devuelve total_rows, invalid_volume, invalid_ohlc, zero_volume, interval_mismatch, duplicates, temporal_gaps.
    """
    try:
        result = await db.execute(
            text("SELECT public.get_candles_quality_report(:sym, :int) AS report"),
            {"sym": symbol or "", "int": interval or ""},
        )
    except Exception:
        return _default_quality_response(symbol, interval)
    row = result.mappings().first()
    if not row or row["report"] is None:
        return _default_quality_response(symbol, interval)
    report = row["report"]
    return report if isinstance(report, dict) else _default_quality_response(symbol, interval)


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
