"""
Módulo compartido de trading y capital: fees, PnL, margen y validaciones.
Reglas:
- entry_notional = quantity * entry_price
- exit_notional = quantity * exit_price
- margin_used_usdt = entry_notional / leverage
"""
from decimal import Decimal
from typing import Literal

# Tipo para maker/taker
MakerTaker = Literal["MAKER", "TAKER"]
PositionSide = Literal["LONG", "SHORT"]


def get_fee_rate(
    maker_fee_bps: float,
    taker_fee_bps: float,
    maker_taker: MakerTaker,
    bnb_discount_pct: float = 0.0,
    vip_tier: float = 0.0,
) -> Decimal:
    """Tasa de fee en decimal (ej: 0.0004 para 4 bps). bnb_discount_pct y vip_tier reducen la tasa."""
    bps = taker_fee_bps if maker_taker == "TAKER" else maker_fee_bps
    rate = Decimal(str(bps)) / Decimal("10000")
    if bnb_discount_pct:
        rate *= Decimal("1") - Decimal(str(bnb_discount_pct)) / Decimal("100")
    if vip_tier:
        rate *= Decimal("1") - Decimal(str(vip_tier)) / Decimal("100")
    return rate


def calc_entry_fee(entry_notional: Decimal, fee_rate: Decimal) -> Decimal:
    return (entry_notional * fee_rate).quantize(Decimal("0.0001"))


def calc_exit_fee(exit_notional: Decimal, fee_rate: Decimal) -> Decimal:
    return (exit_notional * fee_rate).quantize(Decimal("0.0001"))


def calc_gross_pnl(
    position_side: PositionSide,
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
) -> Decimal:
    """PnL bruto: LONG = (exit - entry)*qty, SHORT = (entry - exit)*qty."""
    if position_side == "LONG":
        return ((exit_price - entry_price) * quantity).quantize(Decimal("0.0001"))
    return ((entry_price - exit_price) * quantity).quantize(Decimal("0.0001"))


def calc_net_pnl(
    gross_pnl_usdt: Decimal,
    entry_fee: Decimal,
    exit_fee: Decimal,
    funding_fee: Decimal = Decimal("0"),
    slippage_usdt: Decimal = Decimal("0"),
) -> Decimal:
    return (gross_pnl_usdt - entry_fee - exit_fee - funding_fee - slippage_usdt).quantize(Decimal("0.0001"))


def calc_margin_used(entry_notional: Decimal, leverage: int) -> Decimal:
    """margin_used_usdt = entry_notional / leverage"""
    if leverage <= 0:
        return Decimal("0")
    return (entry_notional / Decimal(str(leverage))).quantize(Decimal("0.0001"))


def cap_quantity_to_limits(
    quantity: Decimal,
    entry_price: Decimal,
    leverage: int,
    equity: Decimal,
    max_notional_usdt: Decimal | None,
    max_notional_pct_of_equity: Decimal | None,
    max_margin_pct_of_equity: Decimal | None,
) -> Decimal:
    """
    Cap quantity para que notional y margen no superen los límites.
    max_* None = sin límite. Devuelve min(quantity, qty_max).
    """
    if entry_price is None or entry_price <= 0 or equity <= 0:
        return quantity
    notional_cap: Decimal | None = None
    if max_notional_usdt is not None and max_notional_usdt > 0:
        notional_cap = max_notional_usdt
    if max_notional_pct_of_equity is not None and max_notional_pct_of_equity > 0:
        cap_pct = equity * (max_notional_pct_of_equity / Decimal("100"))
        notional_cap = min(notional_cap, cap_pct) if notional_cap is not None else cap_pct
    margin_cap: Decimal | None = None
    if max_margin_pct_of_equity is not None and max_margin_pct_of_equity > 0 and leverage > 0:
        margin_cap = equity * (max_margin_pct_of_equity / Decimal("100"))
        notional_by_margin = margin_cap * Decimal(str(leverage))
        notional_cap = min(notional_cap, notional_by_margin) if notional_cap is not None else notional_by_margin
    if notional_cap is None or notional_cap <= 0:
        return quantity
    qty_max = (notional_cap / entry_price).quantize(Decimal("0.00000001"))
    capped = min(quantity, qty_max)
    return max(capped, Decimal("0"))


def validate_can_open_trade(
    available_balance_usdt: Decimal,
    margin_used_usdt: Decimal,
    entry_fee: Decimal,
) -> tuple[bool, str]:
    """
    Valida si hay capital suficiente para abrir el trade.
    Retorna (ok, reason).
    """
    required = margin_used_usdt + entry_fee
    if available_balance_usdt < required:
        return False, f"Capital insuficiente: disponible {available_balance_usdt}, necesario {required} (margen {margin_used_usdt} + fee entrada {entry_fee})"
    return True, ""
