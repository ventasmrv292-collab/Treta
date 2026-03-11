"""
Estrategias puras: reciben velas y parámetros, devuelven señal o None.
Registro por (family, name, version) para el strategy_engine.
"""
from app.services.strategies.breakout import breakout_volume_v1, breakout_volume_v2
from app.services.strategies.mean_reversion import vwap_snapback_v1, vwap_snapback_v2
from app.services.strategies.trend_pullback import ema_pullback_v1, ema_pullback_v2

# (family, name, version) -> callable(candles, params) -> signal | None
STRATEGY_REGISTRY: dict[tuple[str, str, str], callable] = {
    ("BREAKOUT", "breakout_volume_v1", "1.0.0"): breakout_volume_v1,
    ("BREAKOUT", "breakout_volume_v2", "2.0.0"): breakout_volume_v2,
    ("MEAN_REVERSION", "vwap_snapback_v1", "1.0.0"): vwap_snapback_v1,
    ("MEAN_REVERSION", "vwap_snapback_v2", "2.0.0"): vwap_snapback_v2,
    ("TREND_PULLBACK", "ema_pullback_v1", "1.0.0"): ema_pullback_v1,
    ("TREND_PULLBACK", "ema_pullback_v2", "2.0.0"): ema_pullback_v2,
}


def get_strategy_fn(family: str, name: str, version: str):
    return STRATEGY_REGISTRY.get((family, name, version))
