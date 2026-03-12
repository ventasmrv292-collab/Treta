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


def estimate_total_cost_usdt(
    entry_fee: Decimal,
    exit_fee_est: Decimal,
    slippage_est_usdt: Decimal = Decimal("0"),
) -> Decimal:
    """Coste total estimado del trade (entrada + salida + slippage)."""
    return (entry_fee + exit_fee_est + slippage_est_usdt).quantize(Decimal("0.0001"))


def estimate_total_cost_pct(estimated_total_cost_usdt: Decimal, entry_notional: Decimal) -> Decimal | None:
    """Coste total estimado como % del notional. None si entry_notional <= 0."""
    if not entry_notional or entry_notional <= 0:
        return None
    return ((estimated_total_cost_usdt / entry_notional) * 100).quantize(Decimal("0.0001"))


def compute_expected_net_rr(
    entry_price: Decimal,
    take_profit: Decimal,
    stop_loss: Decimal,
    quantity: Decimal,
    position_side: PositionSide,
    entry_fee: Decimal,
    exit_fee_est: Decimal,
    slippage_est_usdt: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Expected net RR ex ante: (net_reward / net_risk).
    net_reward = gross_reward - exit_fee_est; net_risk = gross_risk + entry_fee + slippage_est.
    Retorna (expected_net_rr, expected_net_reward, expected_net_risk).
    """
    entry = entry_price
    tp = take_profit
    stop = stop_loss
    qty = quantity
    if position_side == "LONG":
        gross_reward = (tp - entry) * qty
        gross_risk = (entry - stop) * qty
    else:
        gross_reward = (entry - tp) * qty
        gross_risk = (stop - entry) * qty
    expected_net_reward = (gross_reward - exit_fee_est).quantize(Decimal("0.0001"))
    expected_net_risk = (gross_risk + entry_fee + slippage_est_usdt).quantize(Decimal("0.0001"))
    if expected_net_risk <= 0:
        return Decimal("0"), expected_net_reward, expected_net_risk
    expected_net_rr = (expected_net_reward / expected_net_risk).quantize(Decimal("0.0001"))
    return expected_net_rr, expected_net_reward, expected_net_risk


def compute_min_tp_for_net_rr(
    entry_price: Decimal,
    stop_loss: Decimal,
    quantity: Decimal,
    position_side: PositionSide,
    min_net_rr_ratio: Decimal,
    entry_fee: Decimal,
    fee_rate: Decimal,
    slippage_est_usdt: Decimal = Decimal("0"),
) -> Decimal:
    """
    TP mínimo (precio) para que expected_net_rr = min_net_rr_ratio.
    Considera exit_fee en función del TP: exit_fee = (qty * tp) * fee_rate (LONG) al cerrar en tp.
    LONG: tp_min = (entry + min_net_rr * net_risk / qty) / (1 - fee_rate)
    SHORT: tp_min = (entry - min_net_rr * net_risk / qty) / (1 + fee_rate)
    """
    entry = entry_price
    stop = stop_loss
    qty = quantity
    if qty <= 0:
        return entry
    if position_side == "LONG":
        gross_risk = (entry - stop) * qty
    else:
        gross_risk = (stop - entry) * qty
    net_risk = gross_risk + entry_fee + slippage_est_usdt
    if net_risk <= 0:
        return entry
    # min_net_rr * net_risk = net_reward = gross_reward - exit_fee = qty*(tp*(1-fee_rate) - entry) (LONG)
    # => tp*(1-fee_rate) = entry + min_net_rr*net_risk/qty => tp = (entry + min_net_rr*net_risk/qty) / (1-fee_rate)
    one_minus_fee = Decimal("1") - fee_rate
    one_plus_fee = Decimal("1") + fee_rate
    if one_minus_fee <= 0:
        one_minus_fee = Decimal("0.0001")
    term = min_net_rr_ratio * net_risk / qty
    if position_side == "LONG":
        tp_min = (entry + term) / one_minus_fee
    else:
        tp_min = (entry - term) / one_plus_fee
    return tp_min.quantize(Decimal("0.01"))


def check_tp_within_limits(
    entry_price: Decimal,
    take_profit: Decimal,
    stop_loss: Decimal,
    position_side: PositionSide,
    max_tp_distance_pct: Decimal | None,
    max_tp_rr_ratio: Decimal | None,
) -> tuple[bool, str]:
    """
    Comprueba si el TP está dentro de límites razonables.
    max_tp_distance_pct: máximo |tp - entry|/entry * 100.
    max_tp_rr_ratio: máximo (tp_dist / sl_dist) bruto.
    Retorna (ok, reason).
    """
    entry = entry_price
    tp = take_profit
    stop = stop_loss
    if position_side == "LONG":
        tp_dist = tp - entry
        sl_dist = entry - stop
    else:
        tp_dist = entry - tp
        sl_dist = stop - entry
    if max_tp_distance_pct is not None and entry > 0:
        tp_dist_pct = abs(float(tp_dist) / float(entry)) * 100
        if tp_dist_pct > float(max_tp_distance_pct):
            return False, f"TP distance {round(tp_dist_pct, 2)}% > max_tp_distance_pct={max_tp_distance_pct}"
    if max_tp_rr_ratio is not None and sl_dist and sl_dist > 0:
        rr_bruto = abs(tp_dist) / abs(sl_dist)
        if rr_bruto > float(max_tp_rr_ratio):
            return False, f"TP RR ratio {round(rr_bruto, 2)} > max_tp_rr_ratio={max_tp_rr_ratio}"
    return True, ""
