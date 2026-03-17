"""
Lógica de ejecución de entrada realista: señal -> tipo de orden (MARKET / LIMIT / STOP) o STALE.

Resumen para paper trading y backtesting:

1) Cuándo es MARKET
   - El entry está dentro de entry_tolerance_pct del precio actual → entrada inmediata al precio
     actual (con slippage). No se usa el entry antiguo como fill ficticio.
   - (Desactivado para evitar lookahead.) No se usa high/low de la misma vela que generó la señal
     para rellenar “en la misma barra”. El fill intrabar solo se aplica al evaluar órdenes
     PENDIENTES (creadas en un run anterior) con la vela actual en el motor.

2) Cuándo es LIMIT
   - LONG con entry < current: comprar cuando el precio baje al entry (pullback/snapback).
   - SHORT con entry > current: vender cuando el precio suba al entry.
   - Se crea orden pendiente; el trade solo se abre cuando el precio toca el nivel (o expira).

3) Cuándo es STOP
   - LONG con entry > current: comprar cuando el precio suba al entry (breakout).
   - SHORT con entry < current: vender cuando el precio baje al entry.
   - Se crea orden pendiente; el trade se abre cuando el precio rompe el nivel.

4) Señal atrasada (STALE / EXPIRED / MISSED)
   - Si la desviación |entry - current| / current > max_entry_deviation_pct → no se abre trade
     ni se crea pendiente; la señal se marca STALE.
   - Órdenes pendientes que no se llenan antes de expires_at o expires_after_bars → EXPIRED.
"""
from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.services.strategies.base import StrategySignal


class EntryDecision(NamedTuple):
    """Resultado de clasificar una señal respecto al precio actual."""
    action: str  # "MARKET" | "LIMIT" | "STOP" | "STALE"
    order_type: str  # "MARKET" | "LIMIT" | "STOP" (solo si action no es STALE)
    fill_price: Decimal | None  # Para MARKET: precio a usar (actual/slippage); para LIMIT/STOP es trigger
    reason: str


def _pct_diff(entry: Decimal, current: Decimal) -> Decimal:
    if current <= 0:
        return Decimal("999")
    return abs(entry - current) / current * 100


def classify_entry(
    signal: StrategySignal,
    current_price: Decimal,
    entry_tolerance_pct: Decimal | float | None = 0.1,
    max_entry_deviation_pct: Decimal | float | None = 2.0,
    bar_high: Decimal | None = None,
    bar_low: Decimal | None = None,
) -> EntryDecision:
    """
    Clasifica la señal en MARKET, LIMIT, STOP o STALE según precio actual.

    - entry_tolerance_pct: si la desviación entry vs current está dentro de este %, se permite MARKET.
    - max_entry_deviation_pct: si la desviación supera este %, la señal se marca STALE (no abrir).
    - bar_high/bar_low: NO se usan al clasificar la señal nueva (evitar lookahead). Reservados
      por si en el futuro se modela explícitamente simulación intrabar con documentación clara.
    """
    entry = signal.entry_price
    if entry <= 0 or current_price <= 0:
        return EntryDecision("STALE", "MARKET", None, "INVALID_PRICE")

    tol = Decimal(str(entry_tolerance_pct)) if entry_tolerance_pct is not None else Decimal("0.1")
    max_dev = Decimal(str(max_entry_deviation_pct)) if max_entry_deviation_pct is not None else Decimal("2.0")
    dev_pct = _pct_diff(entry, current_price)

    if dev_pct > max_dev:
        return EntryDecision(
            "STALE",
            "MARKET",
            None,
            f"ENTRY_TOO_FAR: deviation {dev_pct:.2f}% > max {max_dev}%",
        )

    if dev_pct <= tol:
        return EntryDecision(
            "MARKET",
            "MARKET",
            current_price,
            f"WITHIN_TOLERANCE: deviation {dev_pct:.2f}% <= {tol}%",
        )

    is_long = signal.position_side.upper() == "LONG"
    # No same-bar fill aquí: evita lookahead (la señal se genera al cierre; no usar high/low de esa vela).
    # Los fills intrabar solo en _evaluate_pending_orders (órdenes de runs anteriores vs vela actual).

    if is_long:
        if entry > current_price:
            return EntryDecision("STOP", "STOP", entry, "LONG_ENTRY_ABOVE_CURRENT")
        else:
            return EntryDecision("LIMIT", "LIMIT", entry, "LONG_ENTRY_BELOW_CURRENT")
    else:
        if entry < current_price:
            return EntryDecision("STOP", "STOP", entry, "SHORT_ENTRY_BELOW_CURRENT")
        else:
            return EntryDecision("LIMIT", "LIMIT", entry, "SHORT_ENTRY_ABOVE_CURRENT")


def pending_order_triggered(
    order_type: str,
    trigger_price: Decimal,
    position_side: str,
    bar_high: Decimal,
    bar_low: Decimal,
) -> bool:
    """
    Indica si una orden pendiente se habría activado en una vela con high/low dados.

    - LIMIT LONG: comprar cuando el precio baja hasta trigger_price → low <= trigger_price.
    - STOP LONG: comprar cuando el precio sube hasta trigger_price → high >= trigger_price.
    - LIMIT SHORT: vender cuando el precio sube hasta trigger_price → high >= trigger_price.
    - STOP SHORT: vender cuando el precio baja hasta trigger_price → low <= trigger_price.
    """
    is_long = position_side.upper() == "LONG"
    if order_type.upper() == "LIMIT":
        if is_long:
            return bar_low <= trigger_price
        else:
            return bar_high >= trigger_price
    elif order_type.upper() == "STOP":
        if is_long:
            return bar_high >= trigger_price
        else:
            return bar_low <= trigger_price
    return False
