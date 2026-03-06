"""Market data service - Binance Futures (read-only). Fallback a CoinGecko si Binance devuelve 451."""
import logging
import time
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

# Caché para CoinGecko y evitar 429 Too Many Requests
_coingecko_cache: dict[tuple[str, str], tuple[Any, float]] = {}
_PRICE_TTL = 60.0
_KLINES_TTL = 300.0


def _cache_get(key: tuple[str, str], ttl: float) -> Any | None:
    now = time.time()
    if key in _coingecko_cache:
        val, expiry = _coingecko_cache[key]
        if now < expiry:
            return val
        del _coingecko_cache[key]
    return None


def _cache_set(key: tuple[str, str], value: Any, ttl: float) -> None:
    _coingecko_cache[key] = (value, time.time() + ttl)


def _cache_get_stale(key: tuple[str, str]) -> Any | None:
    """Devuelve valor en caché aunque esté expirado (para fallback 429)."""
    if key in _coingecko_cache:
        return _coingecko_cache[key][0]
    return None


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
    """Precio desde CoinGecko; caché 60s para no superar rate limit."""
    key = ("price", symbol.upper())
    cached = _cache_get(key, _PRICE_TTL)
    if cached is not None:
        return cached
    cg_id = COINGECKO_IDS.get(symbol.upper(), "bitcoin")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"},
            )
            r.raise_for_status()
            data = r.json()
        price = Decimal(str(data[cg_id]["usd"]))
        _cache_set(key, price, _PRICE_TTL)
        return price
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            stale = _cache_get_stale(key)
            if stale is not None:
                logger.warning("CoinGecko 429, devolviendo precio en caché")
                return stale
        raise


async def _klines_from_coingecko(symbol: str, limit: int = 300) -> list[dict[str, Any]]:
    """OHLC desde CoinGecko; caché 5 min para no superar rate limit."""
    key = ("klines", symbol.upper())
    cached = _cache_get(key, _KLINES_TTL)
    if cached is not None:
        return cached[-limit:] if len(cached) > limit else cached
    cg_id = COINGECKO_IDS.get(symbol.upper(), "bitcoin")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc",
                params={"vs_currency": "usd", "days": "7"},
            )
            r.raise_for_status()
            data = r.json()
        out = []
        for row in data:
            out.append({
                "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
                "open": Decimal(str(row[1])),
                "high": Decimal(str(row[2])),
                "low": Decimal(str(row[3])),
                "close": Decimal(str(row[4])),
                "volume": Decimal("0"),
            })
        _cache_set(key, out, _KLINES_TTL)
        return out[-limit:] if len(out) > limit else out
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            stale = _cache_get_stale(key)
            if stale is not None:
                logger.warning("CoinGecko 429, devolviendo velas en caché")
                return stale[-limit:] if len(stale) > limit else stale
        raise


def _is_render_or_prefer_coingecko() -> bool:
    """En Render (PORT inyectado) Binance devuelve 451; usar CoinGecko directamente."""
    import os
    return os.environ.get("PORT") is not None or os.environ.get("USE_COINGECKO_FOR_MARKET", "").lower() in ("1", "true", "yes")


class MarketDataService:
    """Fetch OHLCV: Binance por defecto; en Render o con USE_COINGECKO_FOR_MARKET usa CoinGecko (Binance 451)."""

    def __init__(self) -> None:
        self.base_url = settings.binance_futures_rest_url.rstrip("/")
        self._use_coingecko = _is_render_or_prefer_coingecko()

    async def get_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "15m",
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get historical klines. En Render usa CoinGecko; si no, Binance con fallback 451."""
        if self._use_coingecko:
            return await _klines_from_coingecko(symbol, limit)
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
        """Get latest price. En Render usa CoinGecko; si no, Binance con fallback 451."""
        if self._use_coingecko:
            return await _price_from_coingecko(symbol)
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
