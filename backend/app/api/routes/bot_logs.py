"""Bot logs API (auditoría y eventos del bot)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.bot_log import BotLog

router = APIRouter()


@router.get("")
async def list_bot_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    event_type: str | None = Query(None),
    module: str | None = Query(None),
    since: datetime | None = Query(None),
):
    """Lista los últimos bot logs con filtros opcionales."""
    q = select(BotLog).order_by(desc(BotLog.created_at)).limit(limit)
    if event_type:
        q = q.where(BotLog.event_type == event_type)
    if module:
        q = q.where(BotLog.module == module)
    if since:
        q = q.where(BotLog.created_at >= since)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "level": r.level,
            "module": r.module,
            "event_type": r.event_type,
            "message": r.message,
            "context_json": r.context_json,
            "related_trade_id": r.related_trade_id,
            "related_signal_event_id": r.related_signal_event_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
