"""Clasificación de régimen de mercado y reglas conservadoras de permiso LONG."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.strategies.base import StrategySignal

REGIME_BULLISH = "BULLISH"
REGIME_BEARISH = "BEARISH"
REGIME_SIDEWAYS = "SIDEWAYS"
REGIME_TRANSITION = "TRANSITION"
REGIME_HIGH_VOL_DOWNTREND = "HIGH_VOLATILITY_DOWNTREND"


@dataclass(frozen=True)
class MarketRegimeConfig:
    # Cálculo base de tendencia
    ema_fast_period: int = 50
    ema_slow_period: int = 200
    bullish_slope_min_pct: float = 0.02
    bearish_slope_max_pct: float = -0.02
    trend_gap_min_pct: float = 0.18
    # Condiciones propias de SIDEWAYS
    sideways_ema_gap_max_pct: float = 0.12
    sideways_slope_abs_max_pct: float = 0.015
    sideways_price_to_ema50_max_pct: float = 0.20
    sideways_price_to_ema200_max_pct: float = 0.25
    # Caída fuerte + cooldown
    strong_drop_lookback_bars: int = 6
    strong_drop_threshold_pct: float = 1.25
    cooldown_bars_after_strong_drop: int = 3
    # Histéresis
    hysteresis_confirm_bars: int = 2
    hysteresis_immediate_margin_mult: float = 1.4
    # Confirmación fuerte de breakout alcista (en SIDEWAYS)
    strong_breakout_min_pct: float = 0.25
    strong_breakout_min_volume_ratio: float = 1.6


DEFAULT_MARKET_REGIME_CONFIG = MarketRegimeConfig()


@dataclass
class MarketRegimeSnapshot:
    regime: str
    reason: str
    raw_regime: str
    cooldown_active: bool
    cooldown_bars_remaining: int
    timeframe_used: str
    reference_time: datetime | None


@dataclass
class _RegimeState:
    current_regime: str
    pending_regime: str | None
    pending_count: int
    cooldown_remaining: int
    last_open_time: datetime | None


_REGIME_STATE_BY_TIMEFRAME: dict[str, _RegimeState] = {}


def get_reference_timeframe(strategy_timeframe: str, available_timeframes: set[str] | None = None) -> str:
    """
    Usa timeframe superior cuando sea posible:
    - 30m -> 1h
    - 1h -> 4h (fallback 1h)
    """
    available = available_timeframes or set()
    if strategy_timeframe == "30m":
        return "1h" if "1h" in available or not available else strategy_timeframe
    if strategy_timeframe == "1h":
        if "4h" in available:
            return "4h"
        return "1h" if "1h" in available or not available else strategy_timeframe
    if strategy_timeframe == "15m":
        return "30m" if "30m" in available else strategy_timeframe
    return strategy_timeframe


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return ((a - b) / b) * 100.0


def _detect_raw_regime(candles: list[dict[str, Any]], cfg: MarketRegimeConfig) -> tuple[str, str, dict[str, float], bool]:
    closes = [float(c["close"]) for c in candles]
    ema_fast = _ema(closes, cfg.ema_fast_period)
    ema_slow = _ema(closes, cfg.ema_slow_period)
    if len(ema_fast) < 2 or len(ema_slow) < 2:
        return REGIME_TRANSITION, "INSUFFICIENT_EMA_DATA", {}, False

    close = closes[-1]
    e50 = ema_fast[-1]
    e200 = ema_slow[-1]
    slope50_pct = _pct(ema_fast[-1], ema_fast[-2])
    ema_gap_pct = abs(_pct(e50, e200))
    price_to_ema50 = abs(_pct(close, e50))
    price_to_ema200 = abs(_pct(close, e200))

    lookback = min(cfg.strong_drop_lookback_bars, len(closes) - 1)
    strong_drop = False
    drop_pct = 0.0
    if lookback >= 1:
        drop_pct = _pct(close, closes[-1 - lookback])
        strong_drop = drop_pct <= -cfg.strong_drop_threshold_pct

    metrics = {
        "close": close,
        "ema50": e50,
        "ema200": e200,
        "slope50_pct": slope50_pct,
        "ema_gap_pct": ema_gap_pct,
        "price_to_ema50_pct": price_to_ema50,
        "price_to_ema200_pct": price_to_ema200,
        "drop_pct": drop_pct,
    }

    bearish = (
        close < e50
        and e50 < e200
        and slope50_pct <= cfg.bearish_slope_max_pct
        and ema_gap_pct >= cfg.trend_gap_min_pct
    )
    bullish = (
        close > e50
        and e50 > e200
        and slope50_pct >= cfg.bullish_slope_min_pct
        and ema_gap_pct >= cfg.trend_gap_min_pct
    )
    sideways = (
        ema_gap_pct <= cfg.sideways_ema_gap_max_pct
        and abs(slope50_pct) <= cfg.sideways_slope_abs_max_pct
        and price_to_ema50 <= cfg.sideways_price_to_ema50_max_pct
        and price_to_ema200 <= cfg.sideways_price_to_ema200_max_pct
        and not strong_drop
    )

    if bearish:
        return REGIME_BEARISH, "close<EMA50, EMA50<EMA200 y pendiente EMA50 negativa", metrics, strong_drop
    if bullish:
        return REGIME_BULLISH, "close>EMA50, EMA50>EMA200 y pendiente EMA50 positiva", metrics, strong_drop
    if sideways:
        return REGIME_SIDEWAYS, "EMA50/EMA200 cercanas, pendiente EMA50 casi plana y sin caída fuerte", metrics, strong_drop
    return REGIME_TRANSITION, "Estructura mixta/no confirmada (régimen en transición)", metrics, strong_drop


def classify_market_regime(
    *,
    candles: list[dict[str, Any]],
    timeframe_used: str,
    cfg: MarketRegimeConfig = DEFAULT_MARKET_REGIME_CONFIG,
) -> MarketRegimeSnapshot:
    if len(candles) < max(cfg.ema_slow_period, cfg.strong_drop_lookback_bars + 2):
        return MarketRegimeSnapshot(
            regime=REGIME_TRANSITION,
            reason="INSUFFICIENT_CANDLES_FOR_REGIME",
            raw_regime=REGIME_TRANSITION,
            cooldown_active=False,
            cooldown_bars_remaining=0,
            timeframe_used=timeframe_used,
            reference_time=candles[-1].get("open_time") if candles else None,
        )

    raw_regime, raw_reason, metrics, strong_drop = _detect_raw_regime(candles, cfg)
    ref_time = candles[-1].get("open_time")
    state = _REGIME_STATE_BY_TIMEFRAME.get(timeframe_used)
    if state is None:
        state = _RegimeState(
            current_regime=raw_regime,
            pending_regime=None,
            pending_count=0,
            cooldown_remaining=0,
            last_open_time=ref_time,
        )
        _REGIME_STATE_BY_TIMEFRAME[timeframe_used] = state
    else:
        new_bar = ref_time is not None and ref_time != state.last_open_time
        if new_bar and state.cooldown_remaining > 0:
            state.cooldown_remaining -= 1
        if strong_drop and raw_regime in (REGIME_BEARISH, REGIME_TRANSITION):
            state.cooldown_remaining = max(state.cooldown_remaining, cfg.cooldown_bars_after_strong_drop)
        if raw_regime != state.current_regime:
            # Cambio inmediato solo si el margen de tendencia es fuerte.
            strong_margin = metrics.get("ema_gap_pct", 0.0) >= (cfg.trend_gap_min_pct * cfg.hysteresis_immediate_margin_mult)
            if strong_margin and raw_regime in (REGIME_BULLISH, REGIME_BEARISH):
                state.current_regime = raw_regime
                state.pending_regime = None
                state.pending_count = 0
            else:
                if state.pending_regime == raw_regime:
                    state.pending_count += 1
                else:
                    state.pending_regime = raw_regime
                    state.pending_count = 1
                if state.pending_count >= cfg.hysteresis_confirm_bars:
                    state.current_regime = raw_regime
                    state.pending_regime = None
                    state.pending_count = 0
        else:
            state.pending_regime = None
            state.pending_count = 0
        state.last_open_time = ref_time

    cooldown_active = state.cooldown_remaining > 0
    final_regime = state.current_regime
    if cooldown_active and final_regime in (REGIME_BEARISH, REGIME_TRANSITION):
        final_regime = REGIME_HIGH_VOL_DOWNTREND

    reason = raw_reason
    if cooldown_active:
        reason = f"{reason} · cooldown por caída fuerte reciente ({state.cooldown_remaining} velas)"

    return MarketRegimeSnapshot(
        regime=final_regime,
        reason=reason,
        raw_regime=raw_regime,
        cooldown_active=cooldown_active,
        cooldown_bars_remaining=state.cooldown_remaining,
        timeframe_used=timeframe_used,
        reference_time=ref_time,
    )


def _has_strong_breakout_confirmation(signal: StrategySignal | None, cfg: MarketRegimeConfig) -> bool:
    if signal is None:
        return False
    md = signal.metadata or {}
    prev_high = float(md.get("prev_high") or 0.0)
    close = float(md.get("close") or 0.0)
    volume_ratio = float(md.get("volume_ratio") or 0.0)
    if prev_high <= 0 or close <= prev_high:
        return False
    breakout_pct = _pct(close, prev_high)
    return breakout_pct >= cfg.strong_breakout_min_pct and volume_ratio >= cfg.strong_breakout_min_volume_ratio


def evaluate_long_permission(
    *,
    strategy_name: str,
    signal: StrategySignal | None,
    regime: MarketRegimeSnapshot,
    cfg: MarketRegimeConfig = DEFAULT_MARKET_REGIME_CONFIG,
) -> tuple[bool, str]:
    # Conservador por defecto: en transición y regímenes bajistas no se permite LONG.
    if regime.regime in (REGIME_BEARISH, REGIME_HIGH_VOL_DOWNTREND, REGIME_TRANSITION):
        return False, f"MARKET_REGIME_BLOCK: {regime.regime}"

    if strategy_name == "vwap_snapback_v2":
        if regime.regime != REGIME_BULLISH:
            return False, f"MARKET_REGIME_BLOCK: {regime.regime} (VWAP v2 solo permitido en BULLISH)"
        return True, "MARKET_REGIME_ALLOW: BULLISH"

    if strategy_name == "breakout_volume_v2":
        if regime.regime == REGIME_BULLISH:
            return True, "MARKET_REGIME_ALLOW: BULLISH"
        if regime.regime == REGIME_SIDEWAYS:
            if _has_strong_breakout_confirmation(signal, cfg):
                return True, "MARKET_REGIME_ALLOW: SIDEWAYS_STRONG_BREAKOUT_CONFIRMED"
            return False, "MARKET_REGIME_BLOCK: SIDEWAYS_REQUIRES_STRONG_BREAKOUT_CONFIRMATION"
        return False, f"MARKET_REGIME_BLOCK: {regime.regime}"

    # Otras estrategias LONG: conservador pero no extremo (BULLISH/SIDEWAYS).
    if regime.regime in (REGIME_BULLISH, REGIME_SIDEWAYS):
        return True, f"MARKET_REGIME_ALLOW: {regime.regime}"
    return False, f"MARKET_REGIME_BLOCK: {regime.regime}"
