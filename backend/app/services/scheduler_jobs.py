"""
Definición de jobs del scheduler (llamadas a servicios).
Solo timeframes 15m, 30m y 1h. Sin 1m ni 5m.
Cada función es async y sin argumentos; el scheduler las ejecuta con el intervalo correspondiente.
"""
from app.services.candle_sync import sync_candles_to_db
from app.services.strategy_engine import run_strategies_for_timeframe
from app.services.position_supervisor import run_supervisor_cycle

SYMBOL = "BTCUSDT"


async def run_sync_candles_15m() -> None:
    await sync_candles_to_db(SYMBOL, "15m", limit=100)


async def run_sync_candles_30m() -> None:
    await sync_candles_to_db(SYMBOL, "30m", limit=100)


async def run_sync_candles_1h() -> None:
    await sync_candles_to_db(SYMBOL, "1h", limit=100)


async def run_strategies_15m() -> None:
    await run_strategies_for_timeframe("15m")


async def run_strategies_30m() -> None:
    await run_strategies_for_timeframe("30m")


async def run_strategies_1h() -> None:
    await run_strategies_for_timeframe("1h")


async def run_position_supervisor_cycle() -> None:
    await run_supervisor_cycle()


async def run_refresh_analytics_cache() -> None:
    """Opcional: actualizar cache de analytics. Por ahora no-op."""
    pass
