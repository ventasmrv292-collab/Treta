"""Market data API - price, stream status."""
import logging

import httpx
from fastapi import APIRouter, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.candle import Candle
from app.models.strategy import Strategy
from app.models.strategy_runtime_config import StrategyRuntimeConfig
from app.services.market_data import MarketDataService
from app.services.market_regime import (
    DEFAULT_MARKET_REGIME_CONFIG,
    classify_market_regime,
    evaluate_long_permission,
    evaluate_short_permission,
    get_reference_timeframe,
)

router = APIRouter()
logger = logging.getLogger(__name__)

RETRY_AFTER_SECONDS = 90


async def _candles_for_regime(db: AsyncSession, symbol: str, timeframe: str, limit: int = 240) -> list[dict]:
    result = await db.execute(
        select(Candle)
        .where(Candle.symbol == symbol, Candle.interval == timeframe, Candle.is_closed == True)
        .order_by(Candle.open_time.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    return [
        {
            "open_time": c.open_time,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
            "symbol": c.symbol,
        }
        for c in reversed(rows)
    ]


@router.get("/price")
async def get_current_price(symbol: str = Query("BTCUSDT")):
    """Get current mark price for symbol. Incluye 'source' (binance, bybit, coingecko)."""
    try:
        svc = MarketDataService()
        price, source = await svc.get_current_price(symbol=symbol)
        return {"symbol": symbol, "price": str(price), "source": source}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("market/price rate limit (429): %s", e)
            return JSONResponse(
                status_code=503,
                content={"detail": "Límite de solicitudes. Reintenta en 1–2 min.", "retry_after": RETRY_AFTER_SECONDS},
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
            )
        if e.response.status_code in (418, 451):
            logger.warning("market/price Binance %s: %s", e.response.status_code, e.request.url)
            return JSONResponse(
                status_code=502,
                content={
                    "detail": "Binance no disponible desde esta región ({}). Prueba región EU West (Amsterdam).".format(
                        e.response.status_code
                    ),
                    "code": e.response.status_code,
                },
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
    force_binance: bool = Query(False, description="Intentar Binance primero (velas con volumen); si falla 451 se usa CoinGecko"),
):
    """Get klines for chart. Por defecto usa Binance o CoinGecko según configuración; force_binance=1 intenta Binance primero."""
    try:
        svc = MarketDataService()
        klines, source = await svc.get_klines(
            symbol=symbol, interval=interval, limit=limit, force_binance=force_binance
        )
        return {
            "symbol": symbol,
            "interval": interval,
            "source": source,
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
        if e.response.status_code in (418, 451):
            logger.warning("market/klines Binance %s: %s", e.response.status_code, e.request.url)
            return JSONResponse(
                status_code=502,
                content={
                    "detail": "Binance no permite velas desde esta región ({}). Cambia la región del backend a EU West (Amsterdam) o revisa la documentación.".format(
                        e.response.status_code
                    ),
                    "code": e.response.status_code,
                },
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


@router.get("/regime-status")
async def get_regime_status(
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("30m"),
    db: AsyncSession = Depends(get_db),
):
    available = {"15m", "30m", "1h", "4h"}
    primary_regime_tf = get_reference_timeframe(timeframe, available)
    primary_candles = await _candles_for_regime(db, symbol, primary_regime_tf)
    if len(primary_candles) < max(DEFAULT_MARKET_REGIME_CONFIG.ema_slow_period, 60):
        primary_regime_tf = "1h"
        primary_candles = await _candles_for_regime(db, symbol, "1h")
    primary_snapshot = classify_market_regime(
        candles=primary_candles,
        timeframe_used=primary_regime_tf,
    )

    runtime_rows = (
        await db.execute(
            select(StrategyRuntimeConfig, Strategy)
            .join(Strategy, Strategy.id == StrategyRuntimeConfig.strategy_id)
            .where(Strategy.active == True, StrategyRuntimeConfig.active == True, StrategyRuntimeConfig.symbol == symbol)
            .order_by(Strategy.name, StrategyRuntimeConfig.timeframe)
        )
    ).all()

    snapshots_by_tf: dict[str, dict] = {
        primary_regime_tf: {
            "regime": primary_snapshot.regime,
            "reason": primary_snapshot.reason,
            "cooldown_active": primary_snapshot.cooldown_active,
            "cooldown_bars_remaining": primary_snapshot.cooldown_bars_remaining,
            "raw_regime": primary_snapshot.raw_regime,
            "timeframe_used": primary_snapshot.timeframe_used,
        }
    }
    permissions: list[dict] = []
    for rtc, strat in runtime_rows:
        ref_tf = get_reference_timeframe(rtc.timeframe, available)
        candles = await _candles_for_regime(db, symbol, ref_tf)
        if len(candles) < max(DEFAULT_MARKET_REGIME_CONFIG.ema_slow_period, 60):
            ref_tf = "1h"
            candles = await _candles_for_regime(db, symbol, "1h")
        snap = classify_market_regime(candles=candles, timeframe_used=ref_tf)
        snapshots_by_tf[ref_tf] = {
            "regime": snap.regime,
            "reason": snap.reason,
            "cooldown_active": snap.cooldown_active,
            "cooldown_bars_remaining": snap.cooldown_bars_remaining,
            "raw_regime": snap.raw_regime,
            "timeframe_used": snap.timeframe_used,
        }
        if rtc.allow_long:
            long_allowed, long_reason = evaluate_long_permission(
                strategy_name=strat.name,
                signal=None,  # Conservador: sin señal concreta no damos "permitido condicional"
                regime=snap,
            )
        else:
            long_allowed, long_reason = (False, "RUNTIME_CONFIG_BLOCK: allow_long=false")
        if rtc.allow_short:
            short_allowed, short_reason = evaluate_short_permission(
                strategy_name=strat.name,
                signal=None,
                regime=snap,
            )
        else:
            short_allowed, short_reason = (False, "RUNTIME_CONFIG_BLOCK: allow_short=false")
        experiment_tier = None
        if strat.name == "breakout_volume_v2":
            experiment_tier = "principal"
        elif strat.name == "vwap_snapback_v2":
            experiment_tier = "experimental"
        elif strat.name == "ema_pullback_v2":
            experiment_tier = "exploratoria"
        permissions.append(
            {
                "strategy_family": strat.family,
                "strategy_name": strat.name,
                "strategy_version": strat.version,
                "strategy_timeframe": rtc.timeframe,
                "regime_timeframe_used": snap.timeframe_used,
                "long_allowed": bool(long_allowed),
                "long_reason": long_reason,
                "short_allowed": bool(short_allowed),
                "short_reason": short_reason,
                "market_regime": snap.regime,
                "experiment_tier": experiment_tier,
            }
        )

    return {
        "symbol": symbol,
        "requested_timeframe": timeframe,
        "current_regime": {
            "regime": primary_snapshot.regime,
            "reason": primary_snapshot.reason,
            "cooldown_active": primary_snapshot.cooldown_active,
            "cooldown_bars_remaining": primary_snapshot.cooldown_bars_remaining,
            "raw_regime": primary_snapshot.raw_regime,
            "timeframe_used": primary_snapshot.timeframe_used,
        },
        "regimes_by_timeframe": snapshots_by_tf,
        "strategy_long_permissions": permissions,
        "strategy_runtime_permissions": permissions,
    }
