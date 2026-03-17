"""Market data API - price, stream status."""
import logging

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.market_data import MarketDataService

router = APIRouter()
logger = logging.getLogger(__name__)

RETRY_AFTER_SECONDS = 90


@router.get("/price")
async def get_current_price(symbol: str = Query("BTCUSDT")):
    """Get current mark price for symbol."""
    try:
        svc = MarketDataService()
        price = await svc.get_current_price(symbol=symbol)
        return {"symbol": symbol, "price": str(price)}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("market/price rate limit (429): %s", e)
            return JSONResponse(
                status_code=503,
                content={"detail": "Límite de solicitudes. Reintenta en 1–2 min.", "retry_after": RETRY_AFTER_SECONDS},
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
            )
        logger.exception("market/price failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "No se pudo obtener el precio. Reintenta en unos segundos."},
        )
    except Exception as e:
        logger.exception("market/price failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "No se pudo obtener el precio. Reintenta en unos segundos."},
        )


@router.get("/klines")
async def get_klines(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("15m"),
    limit: int = Query(300, le=1500),
):
    """Get klines for chart (from Binance)."""
    try:
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
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("market/klines rate limit (429): %s", e)
            return JSONResponse(
                status_code=503,
                content={"detail": "Límite de solicitudes. Reintenta en 1–2 min.", "retry_after": RETRY_AFTER_SECONDS},
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
            )
        logger.exception("market/klines failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "No se pudieron cargar las velas. Reintenta en unos segundos."},
        )
    except Exception as e:
        logger.exception("market/klines failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "No se pudieron cargar las velas. Reintenta en unos segundos."},
        )
