"""
TREND_PULLBACK / ema_pullback_v1 / 1.0.0
Señal en pullback a EMA en tendencia: precio toca EMA y rebota.
"""
from decimal import Decimal
from typing import Any

from app.services.strategies.base import StrategySignal


def _ema(values: list[float], period: int) -> float:
    if not values or period <= 0:
        return 0.0
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


def ema_pullback_v1(candles: list[dict[str, Any]], params: dict[str, Any] | None) -> StrategySignal | None:
    if not candles or len(candles) < 50:
        return None
    params = params or {}
    ema_period = int(params.get("ema_period", 20))
    touch_pct = float(params.get("touch_pct", 0.1))  # proximidad a EMA para “tocar”
    timeframe = params.get("timeframe", "15m")

    closes = [float(c["close"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    last = closes[-1]
    ema = _ema(closes, ema_period)
    if ema <= 0:
        return None
    # Tendencia: EMA anterior < EMA actual = alcista
    ema_prev = _ema(closes[:-1], ema_period)
    uptrend = ema_prev < ema
    downtrend = ema_prev > ema
    # Pullback: último low cerca de EMA (alcista) o último high cerca de EMA (bajista)
    last_low = lows[-1] if lows else last
    last_high = highs[-1] if highs else last
    near_ema = abs(last - ema) / ema * 100 <= touch_pct or abs(last_low - ema) / ema * 100 <= touch_pct or abs(last_high - ema) / ema * 100 <= touch_pct
    if not near_ema:
        return None
    if uptrend and last >= ema:
        sl_dist = (last - ema) * 0.5
        tp_dist = sl_dist * 2
        return StrategySignal(
            strategy_family="TREND_PULLBACK",
            strategy_name="ema_pullback_v1",
            strategy_version="1.0.0",
            symbol=candles[-1].get("symbol", "BTCUSDT"),
            timeframe=timeframe,
            position_side="LONG",
            entry_price=Decimal(str(last)),
            take_profit=Decimal(str(round(last + tp_dist, 2))),
            stop_loss=Decimal(str(round(last - sl_dist, 2))),
            confidence=0.8,
            metadata={"reason": "ema_pullback_long", "ema": ema},
        )
    if downtrend and last <= ema:
        sl_dist = (ema - last) * 0.5
        tp_dist = sl_dist * 2
        return StrategySignal(
            strategy_family="TREND_PULLBACK",
            strategy_name="ema_pullback_v1",
            strategy_version="1.0.0",
            symbol=candles[-1].get("symbol", "BTCUSDT"),
            timeframe=timeframe,
            position_side="SHORT",
            entry_price=Decimal(str(last)),
            take_profit=Decimal(str(round(last - tp_dist, 2))),
            stop_loss=Decimal(str(round(last + sl_dist, 2))),
            confidence=0.8,
            metadata={"reason": "ema_pullback_short", "ema": ema},
        )
    return None
