"""Signal events API (señales: RECEIVED, ACCEPTED, PENDING_ORDER, STALE, EXPIRED, REJECTED)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.signal_event import SignalEvent

router = APIRouter()


@router.get("")
async def list_signal_events(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(30, ge=1, le=100),
    status: str | None = Query(None, description="Filtrar por status: RECEIVED, ACCEPTED, PENDING_ORDER, STALE, EXPIRED, REJECTED"),
):
    """Lista las últimas señales con su estado (para mostrar MARKET/LIMIT/STOP vía trade; aquí tipo señal)."""
    q = select(SignalEvent).order_by(desc(SignalEvent.created_at)).limit(limit)
    if status:
        q = q.where(SignalEvent.status == status)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "strategy_family": r.strategy_family,
            "strategy_name": r.strategy_name,
            "strategy_version": r.strategy_version,
            "status": r.status,
            "decision_reason": r.decision_reason,
            "trade_id": r.trade_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]
