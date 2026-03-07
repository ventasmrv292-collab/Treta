"""
Sincronización de velas: obtiene velas cerradas de Binance y las guarda en Supabase/DB.
Solo persiste velas cerradas (no la vela actual en formación).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

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
# Binance 1m: 1 candle = 1 min; para no guardar la vela abierta pedimos limit y usamos las que tengan close_time < now
# En Binance klines la última vela es la abierta; las anteriores están cerradas.
DEFAULT_LIMIT = 100


def _close_time_for_interval(open_time: datetime, interval: str) -> datetime | None:
    """Aproximación de close_time según intervalo (Binance: 1m=+1min, 5m=+5min, 15m=+15min)."""
    from datetime import timedelta
    delta = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
    }.get(interval)
    if not delta:
        return None
    return open_time + delta


async def sync_candles_to_db(symbol: str, interval: str, limit: int = DEFAULT_LIMIT) -> int:
    """
    Descarga velas de Binance, filtra solo cerradas (open_time + interval < now) y hace upsert en DB.
    Retorna número de velas insertadas/actualizadas.
    """
    now = datetime.now(timezone.utc)
    svc = MarketDataService()
    klines = await svc.get_klines(symbol=symbol, interval=interval, limit=limit)
    if not klines:
        return 0

    # Filtrar solo velas cerradas: close_time < now
    delta_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(interval, 1)
    from datetime import timedelta
    delta = timedelta(minutes=delta_minutes)
    closed_only = [k for k in klines if _close_time_for_interval(k["open_time"], interval) and (k["open_time"] + delta) <= now]
    if not closed_only:
        return 0

    async with async_session_maker() as session:
        try:
            count = 0
            for k in closed_only:
                stmt = insert(Candle).values(
                    symbol=symbol,
                    interval=interval,
                    open_time=k["open_time"],
                    open=k["open"],
                    high=k["high"],
                    low=k["low"],
                    close=k["close"],
                    volume=k["volume"],
                    close_time=_close_time_for_interval(k["open_time"], interval),
                    is_closed=True,
                    source="BINANCE",
                ).on_conflict_do_update(
                    index_elements=["symbol", "interval", "open_time"],
                    set_={
                        "open": k["open"],
                        "high": k["high"],
                        "low": k["low"],
                        "close": k["close"],
                        "volume": k["volume"],
                        "close_time": _close_time_for_interval(k["open_time"], interval),
                        "is_closed": True,
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
