"""
Motor de position sizing y validación de límites de riesgo.
Sizing: FIXED_QTY | FIXED_NOTIONAL | RISK_PCT_OF_EQUITY.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

# Sizing modes
SIZING_FIXED_QTY = "FIXED_QTY"
SIZING_FIXED_NOTIONAL = "FIXED_NOTIONAL"
SIZING_RISK_PCT = "RISK_PCT_OF_EQUITY"


def calc_position_size_by_fixed_qty(fixed_quantity: Decimal) -> Decimal:
    """Retorna la cantidad fija (sin dependencia de precio/cuenta)."""
    if fixed_quantity is None or fixed_quantity <= 0:
        return Decimal("0")
    return fixed_quantity.quantize(Decimal("0.00000001"))


def calc_position_size_by_fixed_notional(
    fixed_notional_usdt: Decimal,
    entry_price: Decimal,
) -> Decimal:
    """quantity = fixed_notional_usdt / entry_price."""
    if not fixed_notional_usdt or not entry_price or entry_price <= 0:
        return Decimal("0")
    return (fixed_notional_usdt / entry_price).quantize(Decimal("0.00000001"))


def calc_position_size_by_risk_pct(
    entry_price: Decimal,
    stop_loss: Decimal | None,
    account_equity: Decimal,
    risk_pct_per_trade: Decimal,
    position_side: str,
) -> Decimal:
    """
    Tamaño por riesgo: riesgo_usdt = equity * risk_pct; por contrato riesgo = |entry - stop| * qty.
    qty = riesgo_usdt / (|entry - stop|) con entry_price en USDT por unidad.
    Si no hay stop_loss retorna 0 (no se puede calcular riesgo).
    """
    if not stop_loss or stop_loss <= 0 or not entry_price or entry_price <= 0:
        return Decimal("0")
    if not account_equity or account_equity <= 0 or not risk_pct_per_trade or risk_pct_per_trade <= 0:
        return Decimal("0")
    risk_usdt = (account_equity * risk_pct_per_trade / Decimal("100")).quantize(Decimal("0.0001"))
    distance = abs(entry_price - stop_loss)
    if distance <= 0:
        return Decimal("0")
    # Por contrato (1 unidad): PnL por unidad = (exit - entry) para LONG, (entry - exit) para SHORT
    # risk_usdt = qty * distance  =>  qty = risk_usdt / distance
    qty = (risk_usdt / distance).quantize(Decimal("0.00000001"))
    return max(Decimal("0"), qty)


def parse_allowed_leverage(allowed_leverage_json: str | None) -> list[int]:
    """Parsea allowed_leverage_json (ej: [10, 20]) y retorna lista de leverages permitidos."""
    if not allowed_leverage_json or not allowed_leverage_json.strip():
        return []  # vacío = no restricción (todos permitidos en validate)
    try:
        data = json.loads(allowed_leverage_json)
        if isinstance(data, list):
            return [int(x) for x in data if isinstance(x, (int, float))]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def validate_risk_limits(
    account_equity: Decimal,
    available_balance: Decimal,
    used_margin: Decimal,
    open_positions_count: int,
    daily_realized_pnl: Decimal,
    profile: Any,
    new_trade_margin: Decimal,
    new_trade_leverage: int,
    consecutive_losses: int = 0,
) -> tuple[bool, str]:
    """
    Valida si se puede abrir el trade según el risk profile.
    profile debe tener: max_open_positions, max_margin_pct_of_account,
    max_daily_loss_usdt, max_daily_loss_pct, cooldown_after_losses, allowed_leverage_json.
    Retorna (ok, mensaje).
    """
    if open_positions_count >= getattr(profile, "max_open_positions", 999):
        return False, f"Límite de posiciones abiertas alcanzado: {open_positions_count} >= {profile.max_open_positions}"

    max_margin_pct = getattr(profile, "max_margin_pct_of_account", None) or Decimal("100")
    total_margin_after = used_margin + new_trade_margin
    if account_equity and account_equity > 0:
        margin_pct = (total_margin_after / account_equity * Decimal("100")).quantize(Decimal("0.01"))
        if margin_pct > max_margin_pct:
            return False, f"Margen total superaría {max_margin_pct}% del equity: {margin_pct}%"

    max_daily_usdt = getattr(profile, "max_daily_loss_usdt", None)
    if max_daily_usdt is not None and daily_realized_pnl < -abs(Decimal(str(max_daily_usdt))):
        return False, f"Pérdida diaria máxima alcanzada: {daily_realized_pnl} (límite {max_daily_usdt} USDT)"

    max_daily_pct = getattr(profile, "max_daily_loss_pct", None)
    if max_daily_pct is not None and account_equity and account_equity > 0:
        daily_loss_pct = (daily_realized_pnl / account_equity * Decimal("100")).quantize(Decimal("0.01"))
        if daily_loss_pct < -abs(Decimal(str(max_daily_pct))):
            return False, f"Pérdida diaria % alcanzada: {daily_loss_pct}% (límite {max_daily_pct}%)"

    cooldown = getattr(profile, "cooldown_after_losses", None)
    if cooldown is not None and consecutive_losses >= cooldown:
        return False, f"Cooldown activo: {consecutive_losses} pérdidas consecutivas (límite {cooldown})"

    allowed = parse_allowed_leverage(getattr(profile, "allowed_leverage_json", None))
    if allowed and new_trade_leverage not in allowed:
        return False, f"Leverage {new_trade_leverage} no permitido por el perfil. Permitidos: {allowed}"

    return True, ""
