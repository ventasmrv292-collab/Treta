"""Market data API - price, stream status."""
from decimal import Decimal
from fastapi import APIRouter, Query

from app.services.market_data import MarketDataService

router = APIRouter()


@router.get("/price")
async def get_current_price(symbol: str = Query("BTCUSDT")):
    """Get current mark price for symbol."""
    svc = MarketDataService()
    price = await svc.get_current_price(symbol=symbol)
    return {"symbol": symbol, "price": str(price)}


@router.get("/klines")
async def get_klines(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("15m"),
    limit: int = Query(300, le=1500),
):
    """Get klines for chart (from Binance)."""
    svc = MarketDataService()
    klines = await svc.get_klines(symbol=symbol, interval=interval, limit=limit)
    return {
        "symbol": symbol,
        "interval": interval,
        "candles": [
            {
                "time": int(k["open_time"].timestamp()),
                "open": float(k["open"]),
                "high": float(k["high"]),
                "low": float(k["low"]),
                "close": float(k["close"]),
                "volume": float(k["volume"]),
            }
            for k in klines
        ],
    }
