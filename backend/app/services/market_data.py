"""Market data service - Binance USDⓈ-M perpetual (USDM) only."""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Set

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
}


def _parse_kline(row: list[Any]) -> dict[str, Any]:
    """Parse Binance kline array to dict (USDM)."""
    return {
        "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
        "open": Decimal(str(row[1])),
        "high": Decimal(str(row[2])),
        "low": Decimal(str(row[3])),
        "close": Decimal(str(row[4])),
        "volume": Decimal(str(row[5])),
    }


class MarketDataService:
    """Fetch OHLCV exclusivamente desde Binance USDⓈ-M Futures (USDM perpetual)."""

    def __init__(self) -> None:
        self.base_url = settings.binance_futures_rest_url.rstrip("/")
        # Caché de símbolos válidos USDM (ej: BTCUSDT, ETHUSDT).
        self._usdm_symbols: Optional[Set[str]] = None

    async def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "15m",
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get historical klines desde Binance USDM (sin fallback a spot)."""
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
        """Get latest price desde Binance USDM (ticker price)."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{self.base_url}/fapi/v1/ticker/price",
                params={"symbol": symbol},
            )
            r.raise_for_status()
            data = r.json()
        return Decimal(data["price"])

    async def get_current_price_with_freshness(
        self, symbol: str = "BTCUSDT"
    ) -> tuple[Decimal, bool]:
        """Para USDM asumimos datos frescos; no hay fallback ni caché externa."""
        price = await self.get_current_price(symbol)
        return price, False

    async def is_valid_usdm_perpetual_symbol(self, symbol: str) -> bool:
        """Valida que el símbolo exista realmente en Binance USDM (`/fapi/v1/exchangeInfo`)."""
        if self._usdm_symbols is None:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(f"{self.base_url}/fapi/v1/exchangeInfo")
                    r.raise_for_status()
                    data = r.json()
                symbols = {
                    s["symbol"]
                    for s in data.get("symbols", [])
                    if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"
                }
                self._usdm_symbols = symbols
            except Exception as e:
                logger.error("No se pudo cargar exchangeInfo USDM: %s", e)
                raise
        return symbol.upper() in (self._usdm_symbols or set())
