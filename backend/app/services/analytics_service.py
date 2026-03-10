"""
Servicio de analytics: resumen, por estrategia, por leverage, curva de equity, recomendaciones de runtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade


async def get_runtime_recommendations(db: AsyncSession, days: int = 7) -> dict:
    """
    Diagnóstico del rendimiento reciente: mejor/peor estrategia, mejor/peor timeframe,
    rendimiento por side (LONG/SHORT) y recomendaciones operativas simples.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    closed = (Trade.status == "CLOSED") & (Trade.closed_at >= cutoff)

    by_strategy = await db.execute(
        select(
            Trade.strategy_name,
            func.coalesce(func.sum(Trade.net_pnl_usdt), 0).label("net_pnl"),
        ).where(closed).group_by(Trade.strategy_name)
    )
    strat_rows = list(by_strategy.all())
    best_strategy = max(strat_rows, key=lambda r: float(r.net_pnl or 0), default=None)
    worst_strategy = min(strat_rows, key=lambda r: float(r.net_pnl or 0), default=None)

    by_side = await db.execute(
        select(
            Trade.position_side,
            func.coalesce(func.sum(Trade.net_pnl_usdt), 0).label("net_pnl"),
        ).where(closed).group_by(Trade.position_side)
    )
    side_rows = list(by_side.all())
    worst_side = min(side_rows, key=lambda r: float(r.net_pnl or 0), default=None)

    by_tf = await db.execute(
        select(
            Trade.timeframe,
            func.coalesce(func.sum(Trade.net_pnl_usdt), 0).label("net_pnl"),
        ).where(closed).group_by(Trade.timeframe)
    )
    tf_rows = list(by_tf.all())
    best_tf = max(tf_rows, key=lambda r: float(r.net_pnl or 0), default=None)
    worst_tf = min(tf_rows, key=lambda r: float(r.net_pnl or 0), default=None)

    recommendations: list[str] = []
    if worst_side and worst_side.position_side == "SHORT" and float(worst_side.net_pnl or 0) < 0:
        recommendations.append("Considera desactivar SHORT en estrategias con peor rendimiento reciente.")
    if worst_strategy and float(worst_strategy.net_pnl or 0) < 0:
        recommendations.append(f"Revisar o pausar temporalmente la estrategia {worst_strategy.strategy_name}.")
    if worst_tf and float(worst_tf.net_pnl or 0) < 0 and best_tf and best_tf.timeframe == "15m":
        recommendations.append("Reducir actividad en 1m/5m y priorizar 15m, que muestra mejor rendimiento reciente.")
    if not recommendations:
        recommendations.append("Mantener configuración actual; no se detectan problemas graves en el periodo analizado.")

    def _strat(r):
        return {"strategy_name": r[0], "net_pnl": float(r[1] or 0)} if r else None
    def _side(r):
        return {"position_side": r[0], "net_pnl": float(r[1] or 0)} if r else None
    def _tf(r):
        return {"timeframe": r[0], "net_pnl": float(r[1] or 0)} if r else None

    return {
        "window_days": days,
        "best_strategy": _strat(best_strategy),
        "worst_strategy": _strat(worst_strategy),
        "best_timeframe": _tf(best_tf),
        "worst_timeframe": _tf(worst_tf),
        "side_performance": [_side(r) for r in side_rows],
        "recommendations": recommendations,
    }


__all__ = ["get_runtime_recommendations"]
