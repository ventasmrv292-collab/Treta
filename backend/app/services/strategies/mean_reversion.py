"""
MEAN_REVERSION / vwap_snapback_v1 / 1.0.0
Señal cuando el precio se aleja del “VWAP” (aquí media móvil simple) y vuelve (snapback).
"""
from decimal import Decimal
from typing import Any

from app.services.strategies.base import StrategySignal


def _sma(values: list[float], n: int) -> float:
    if not values or n <= 0:
        return 0.0
    window = values[-n:]
    return sum(window) / len(window)


def vwap_snapback_v1(candles: list[dict[str, Any]], params: dict[str, Any] | None) -> StrategySignal | None:
    if not candles or len(candles) < 30:
        return None
    params = params or {}
    ma_period = int(params.get("ma_period", 20))
    deviation_pct = float(params.get("deviation_pct", 0.3))  # % de desviación para señal
    timeframe = params.get("timeframe", "15m")

    closes = [float(c["close"]) for c in candles]
    last = closes[-1]
    ma = _sma(closes, ma_period)
    if ma <= 0:
        return None
    dev_pct = abs(last - ma) / ma * 100
    if dev_pct < deviation_pct:
        return None
    # Precio por debajo de la media -> LONG (snapback al alza); por encima -> SHORT
    if last < ma:
        sl_dist = (ma - last) * 0.5
        tp_dist = ma - last
        return StrategySignal(
            strategy_family="MEAN_REVERSION",
            strategy_name="vwap_snapback_v1",
            strategy_version="1.0.0",
            symbol=candles[-1].get("symbol", "BTCUSDT"),
            timeframe=timeframe,
            position_side="LONG",
            entry_price=Decimal(str(last)),
            take_profit=Decimal(str(round(ma, 2))),
            stop_loss=Decimal(str(round(last - sl_dist, 2))),
            confidence=0.75,
            metadata={"reason": "snapback_long", "ma": ma, "deviation_pct": dev_pct},
        )
    if last > ma:
        sl_dist = (last - ma) * 0.5
        return StrategySignal(
            strategy_family="MEAN_REVERSION",
            strategy_name="vwap_snapback_v1",
            strategy_version="1.0.0",
            symbol=candles[-1].get("symbol", "BTCUSDT"),
            timeframe=timeframe,
            position_side="SHORT",
            entry_price=Decimal(str(last)),
            take_profit=Decimal(str(round(ma, 2))),
            stop_loss=Decimal(str(round(last + sl_dist, 2))),
            confidence=0.75,
            metadata={"reason": "snapback_short", "ma": ma, "deviation_pct": dev_pct},
        )
    return None


def vwap_snapback_v2(candles: list[dict[str, Any]], params: dict[str, Any] | None) -> StrategySignal | None:
    """v2: deviation_pct 0.4, sl_factor 0.6, solo LONG; TP para RR >= min_rr_ratio."""
    if not candles or len(candles) < 30:
        return None
    params = params or {}
    ma_period = int(params.get("ma_period", 20))
    deviation_pct = float(params.get("deviation_pct", 0.4))
    sl_factor = float(params.get("sl_factor", 0.6))
    min_rr = float(params.get("min_rr_ratio", 1.0))
    timeframe = params.get("timeframe", "15m")

    closes = [float(c["close"]) for c in candles]
    last = closes[-1]
    ma = _sma(closes, ma_period)
    if ma <= 0:
        return None
    dev_pct = abs(last - ma) / ma * 100
    if dev_pct < deviation_pct:
        return None
    if last >= ma:
        return None
    sl_dist = (ma - last) * sl_factor
    tp_dist = sl_dist * min_rr
    return StrategySignal(
        strategy_family="MEAN_REVERSION",
        strategy_name="vwap_snapback_v2",
        strategy_version="2.0.0",
        symbol=candles[-1].get("symbol", "BTCUSDT"),
        timeframe=timeframe,
        position_side="LONG",
        entry_price=Decimal(str(last)),
        take_profit=Decimal(str(round(last + tp_dist, 2))),
        stop_loss=Decimal(str(round(last - sl_dist, 2))),
        confidence=0.75,
        metadata={"reason": "snapback_long_v2", "ma": ma, "deviation_pct": dev_pct},
    )
