"""
BREAKOUT / breakout_volume_v1 / 1.0.0
Señal cuando el precio cierra por encima del máximo reciente con volumen por encima de la media.
"""
from decimal import Decimal
from typing import Any

from app.services.strategies.base import StrategySignal


def breakout_volume_v1(candles: list[dict[str, Any]], params: dict[str, Any] | None) -> StrategySignal | None:
    if not candles or len(candles) < 20:
        return None
    params = params or {}
    lookback = int(params.get("lookback", 10))
    vol_mult = float(params.get("volume_mult", 1.2))
    atr_pct_sl = float(params.get("atr_pct_sl", 0.5))  # stop loss como % del ATR

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    volumes = [float(c["volume"]) for c in candles]
    last = closes[-1]
    prev_high = max(highs[-lookback-1:-1] or [0])
    avg_vol = sum(volumes[-lookback-1:-1]) / max(len(volumes[-lookback-1:-1]), 1)
    last_vol = volumes[-1] if volumes else 0

    # Breakout alcista: cierre > máximo de lookback y volumen > media
    if last > prev_high and last_vol >= avg_vol * vol_mult and prev_high > 0:
        atr = sum(abs(closes[i] - closes[i-1]) for i in range(-20, 0)) / 20 if len(closes) >= 20 else last * 0.01
        sl_dist = last * (atr_pct_sl * atr / last) if atr else last * 0.005
        tp_dist = sl_dist * 2  # 2:1
        return StrategySignal(
            strategy_family="BREAKOUT",
            strategy_name="breakout_volume_v1",
            strategy_version="1.0.0",
            symbol=candles[-1].get("symbol", "BTCUSDT"),
            timeframe=params.get("timeframe", "15m"),
            position_side="LONG",
            entry_price=Decimal(str(last)),
            take_profit=Decimal(str(round(last + tp_dist, 2))),
            stop_loss=Decimal(str(round(last - sl_dist, 2))),
            confidence=0.8,
            metadata={"reason": "breakout_volume", "prev_high": prev_high, "volume_ratio": last_vol / avg_vol if avg_vol else 0},
        )
    return None


def breakout_volume_v2(candles: list[dict[str, Any]], params: dict[str, Any] | None) -> StrategySignal | None:
    """v2: stop más ancho (atr_pct_sl 1.2), lookback 14, volume_mult 1.4, SL mínimo por min_stop_distance_pct, TP para RR >= min_rr_ratio."""
    if not candles or len(candles) < 20:
        return None
    params = params or {}
    lookback = int(params.get("lookback", 14))
    vol_mult = float(params.get("volume_mult", 1.4))
    atr_pct_sl = float(params.get("atr_pct_sl", 1.2))
    min_stop_pct = float(params.get("min_stop_distance_pct", 0.25)) / 100.0
    min_rr = float(params.get("min_rr_ratio", 1.2))

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    volumes = [float(c["volume"]) for c in candles]
    last = closes[-1]
    prev_high = max(highs[-lookback - 1 : -1] or [0])
    avg_vol = sum(volumes[-lookback - 1 : -1]) / max(len(volumes[-lookback - 1 : -1]), 1)
    last_vol = volumes[-1] if volumes else 0

    if last <= prev_high or prev_high <= 0 or last_vol < avg_vol * vol_mult:
        return None

    atr = (
        sum(abs(closes[i] - closes[i - 1]) for i in range(-20, 0)) / 20
        if len(closes) >= 20
        else last * 0.01
    )
    sl_dist_atr = (atr_pct_sl * atr) if atr else last * 0.005
    sl_dist_min = last * min_stop_pct
    sl_dist = max(sl_dist_atr, sl_dist_min)
    tp_dist = sl_dist * min_rr
    return StrategySignal(
        strategy_family="BREAKOUT",
        strategy_name="breakout_volume_v2",
        strategy_version="2.0.0",
        symbol=candles[-1].get("symbol", "BTCUSDT"),
        timeframe=params.get("timeframe", "15m"),
        position_side="LONG",
        entry_price=Decimal(str(last)),
        take_profit=Decimal(str(round(last + tp_dist, 2))),
        stop_loss=Decimal(str(round(last - sl_dist, 2))),
        confidence=0.8,
        metadata={
            "reason": "breakout_volume_v2",
            "prev_high": prev_high,
            "volume_ratio": last_vol / avg_vol if avg_vol else 0,
            "sl_dist_pct": round(sl_dist / last * 100, 4),
        },
    )
