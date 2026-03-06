"""Market data service - Binance Futures klines (read-only)."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings

INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
}


def _parse_kline(row: list[Any]) -> dict[str, Any]:
    """Parse Binance kline array to dict."""
    return {
        "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
        "open": Decimal(str(row[1])),
        "high": Decimal(str(row[2])),
        "low": Decimal(str(row[3])),
        "close": Decimal(str(row[4])),
        "volume": Decimal(str(row[5])),
    }


class MarketDataService:
    """Fetch OHLCV from Binance Futures API (public, no keys)."""

    def __init__(self) -> None:
        self.base_url = settings.binance_futures_rest_url.rstrip("/")

    async def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "15m",
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get historical klines from Binance Futures."""
        interval = INTERVAL_MAP.get(interval, interval)
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1500),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{self.base_url}/fapi/v1/klines", params=params)
            r.raise_for_status()
            data = r.json()

        return [_parse_kline(row) for row in data]

    async def get_current_price(self, symbol: str = "BTCUSDT") -> Decimal:
        """Get latest mark price for symbol."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/fapi/v1/ticker/price", params={"symbol": symbol})
            r.raise_for_status()
            data = r.json()
        return Decimal(data["price"])
