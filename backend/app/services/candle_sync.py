"""
Sincronización de velas: obtiene velas cerradas de Binance Futures y las guarda en Supabase/DB.
Solo persiste velas cerradas (close_time < now). Usa solo Binance (no CoinGecko) para garantizar
intervalos 1m/5m/15m correctos. Validación previa: OHLC coherente, volume >= 0, close_time desde API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import and_

from app.db.session import async_session_maker
from app.models.candle import Candle
from app.services.market_data import MarketDataService
from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_CANDLES,
    EVENT_CANDLES_SYNC_OK,
    EVENT_CANDLES_SYNC_ERROR,
)

logger = logging.getLogger(__name__)

SYMBOL = "BTCUSDT"
DEFAULT_LIMIT = 100

INTERVAL_DELTA = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
}


def _close_time_for_interval(open_time: datetime, interval: str) -> datetime | None:
    """close_time cuando la API no lo devuelve (fallback)."""
    delta = INTERVAL_DELTA.get(interval)
    return (open_time + delta) if delta else None


def _validate_kline(k: dict) -> tuple[bool, str]:
    """
    Valida OHLC y volume. Devuelve (True, '') si es válido, (False, motivo) si no.
    No insertamos velas con volume < 0 o OHLC incoherente.
    """
    try:
        o = float(k["open"])
        h = float(k["high"])
        l = float(k["low"])
        c = float(k["close"])
        v = float(k["volume"])
    except (TypeError, ValueError, KeyError) as e:
        return False, f"parse: {e}"
    if v < 0:
        return False, "volume < 0"
    if o <= 0 or h <= 0 or l <= 0 or c <= 0:
        return False, "OHLC not positive"
    if h < max(o, c, l) or l > min(o, c, h):
        return False, "high/low inconsistent"
    return True, ""


async def sync_candles_to_db(symbol: str, interval: str, limit: int = DEFAULT_LIMIT) -> int:
    """
    Descarga velas de Binance Futures (force_binance=True), filtra solo cerradas (close_time < now),
    valida cada vela y hace upsert por (symbol, interval, open_time). No inserta velas abiertas ni inválidas.
    """
    now = datetime.now(timezone.utc)
    svc = MarketDataService()
    try:
        klines, _ = await svc.get_klines(
            symbol=symbol, interval=interval, limit=limit, force_binance=True
        )
    except Exception as e:
        err_msg = f"Binance no disponible: {e}"
        logger.warning("candle_sync: %s", err_msg)
        async with async_session_maker() as log_session:
            await bot_log_event(
                log_session,
                "ERROR",
                MODULE_CANDLES,
                EVENT_CANDLES_SYNC_ERROR,
                err_msg,
                context={"symbol": symbol, "interval": interval, "error": str(e)},
            )
            await log_session.commit()
        # No re-lanzar: en regiones con 451 el job termina sin insertar; el scheduler sigue estable.
        return 0
    if not klines:
        return 0

    # Usar close_time de Binance cuando venga; si no, calcular
    closed_only = []
    for k in klines:
        ct = k.get("close_time")
        if ct is None:
            ct = _close_time_for_interval(k["open_time"], interval)
        if ct is None or ct > now:
            continue
        k["close_time"] = ct
        ok, reason = _validate_kline(k)
        if not ok:
            logger.debug("candle_sync: skip invalid kline open_time=%s: %s", k["open_time"], reason)
            continue
        closed_only.append(k)

    if not closed_only:
        return 0

    async with async_session_maker() as session:
        try:
            count = 0
            for k in closed_only:
                ct = k["close_time"]
                values = {
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": k["open_time"],
                    "open": k["open"],
                    "high": k["high"],
                    "low": k["low"],
                    "close": k["close"],
                    "volume": k["volume"],
                    "close_time": ct,
                    "is_closed": True,
                    "source": "BINANCE",
                    "validation_status": "VALID",
                }
                if k.get("quote_volume") is not None:
                    values["quote_volume"] = k["quote_volume"]
                if k.get("trade_count") is not None:
                    values["trade_count"] = k["trade_count"]
                if k.get("taker_buy_base_volume") is not None:
                    values["taker_buy_base_volume"] = k["taker_buy_base_volume"]
                if k.get("taker_buy_quote_volume") is not None:
                    values["taker_buy_quote_volume"] = k["taker_buy_quote_volume"]

                stmt = insert(Candle).values(**values).on_conflict_do_update(
                    index_elements=["symbol", "interval", "open_time"],
                    set_={
                        "open": k["open"],
                        "high": k["high"],
                        "low": k["low"],
                        "close": k["close"],
                        "volume": k["volume"],
                        "close_time": ct,
                        "is_closed": True,
                        "updated_at": datetime.now(timezone.utc),
                        "validation_status": "VALID",
                        "quote_volume": k.get("quote_volume"),
                        "trade_count": k.get("trade_count"),
                        "taker_buy_base_volume": k.get("taker_buy_base_volume"),
                        "taker_buy_quote_volume": k.get("taker_buy_quote_volume"),
                    },
                )
                await session.execute(stmt)
                count += 1
            await bot_log_event(
                session,
                "INFO",
                MODULE_CANDLES,
                EVENT_CANDLES_SYNC_OK,
                f"Sync {symbol} {interval}: {count} velas cerradas",
                context={"symbol": symbol, "interval": interval, "count": count},
            )
            await session.commit()
            logger.info("candle_sync: %s %s saved %d closed candles", symbol, interval, count)
            return count
        except Exception as e:
            await session.rollback()
            logger.exception("candle_sync failed: %s", e)
            async with async_session_maker() as log_session:
                await bot_log_event(
                    log_session,
                    "ERROR",
                    MODULE_CANDLES,
                    EVENT_CANDLES_SYNC_ERROR,
                    f"Sync {symbol} {interval}: {e}",
                    context={"symbol": symbol, "interval": interval, "error": str(e)},
                )
                await log_session.commit()
            raise
