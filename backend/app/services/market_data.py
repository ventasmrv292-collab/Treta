"""Market data service - Binance Futures (read-only). Fallback a CoinGecko si Binance devuelve 451."""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
}

COINGECKO_IDS = {"BTCUSDT": "bitcoin", "BTC": "bitcoin"}


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


async def _price_from_coingecko(symbol: str) -> Decimal:
    """Precio actual desde CoinGecko (fallback cuando Binance devuelve 451)."""
    cg_id = COINGECKO_IDS.get(symbol.upper(), "bitcoin")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": cg_id, "vs_currencies": "usd"},
        )
        r.raise_for_status()
        data = r.json()
    return Decimal(str(data[cg_id]["usd"]))


async def _klines_from_coingecko(symbol: str, limit: int = 300) -> list[dict[str, Any]]:
    """OHLC desde CoinGecko (máx 7 días, sin volumen). Fallback cuando Binance bloquea (451)."""
    cg_id = COINGECKO_IDS.get(symbol.upper(), "bitcoin")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc",
            params={"vs_currency": "usd", "days": "7"},
        )
        r.raise_for_status()
        data = r.json()
    # CoinGecko: [timestamp_ms, open, high, low, close]
    out = []
    for row in data[-limit:]:
        out.append({
            "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
            "open": Decimal(str(row[1])),
            "high": Decimal(str(row[2])),
            "low": Decimal(str(row[3])),
            "close": Decimal(str(row[4])),
            "volume": Decimal("0"),
        })
    return out


class MarketDataService:
    """Fetch OHLCV from Binance Futures. Si Binance devuelve 451 (bloqueo regional), usa CoinGecko."""

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
        """Get historical klines. Binance primero; si 451, fallback CoinGecko."""
        try:
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
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 451:
                logger.warning("Binance 451 (bloqueo regional), usando CoinGecko para velas")
                return await _klines_from_coingecko(symbol, limit)
            raise
        except Exception:
            raise

    async def get_current_price(self, symbol: str = "BTCUSDT") -> Decimal:
        """Get latest price. Binance primero; si 451, fallback CoinGecko."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{self.base_url}/fapi/v1/ticker/price",
                    params={"symbol": symbol},
                )
                r.raise_for_status()
                data = r.json()
            return Decimal(data["price"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 451:
                logger.warning("Binance 451 (bloqueo regional), usando CoinGecko para precio")
                return await _price_from_coingecko(symbol)
            raise
        except Exception:
            raise
