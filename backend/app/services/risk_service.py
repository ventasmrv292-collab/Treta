"""
Servicio de riesgo: reexporta el motor de risk_management para uso en backend.
Sizing y validación de límites (max positions, margin %, daily loss, cooldown, leverage).
"""
from app.services.risk_management import (
    SIZING_FIXED_QTY,
    SIZING_FIXED_NOTIONAL,
    SIZING_RISK_PCT,
    calc_position_size_by_fixed_qty,
    calc_position_size_by_fixed_notional,
    calc_position_size_by_risk_pct,
    parse_allowed_leverage,
    validate_risk_limits,
)

__all__ = [
    "SIZING_FIXED_QTY",
    "SIZING_FIXED_NOTIONAL",
    "SIZING_RISK_PCT",
    "calc_position_size_by_fixed_qty",
    "calc_position_size_by_fixed_notional",
    "calc_position_size_by_risk_pct",
    "parse_allowed_leverage",
    "validate_risk_limits",
]
