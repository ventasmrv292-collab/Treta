"""Servicio de registro de eventos del bot (auditoría y logs operativos)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_log import BotLog

MODULE_TRADE = "trade_service"
MODULE_SUPERVISOR = "supervisor"
MODULE_WEBHOOK = "webhook"
MODULE_RISK = "risk_management"
MODULE_SCHEDULER = "scheduler"
MODULE_STRATEGY = "strategy_engine"
MODULE_CANDLES = "candle_sync"

EVENT_SIGNAL_RECEIVED = "SIGNAL_RECEIVED"
EVENT_SIGNAL_REJECTED = "SIGNAL_REJECTED"
EVENT_STRATEGY_SIGNAL_CREATED = "STRATEGY_SIGNAL_CREATED"
EVENT_TRADE_OPENED = "TRADE_OPENED"
EVENT_TRADE_CLOSED = "TRADE_CLOSED"
EVENT_TP_HIT = "TP_HIT"
EVENT_SL_HIT = "SL_HIT"
EVENT_DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"
EVENT_RISK_LIMIT_BLOCK = "RISK_LIMIT_BLOCK"
EVENT_SUPERVISOR_ERROR = "SUPERVISOR_ERROR"
EVENT_SUPERVISOR_PNL_UPDATE = "SUPERVISOR_PNL_UPDATE"
EVENT_SUPERVISOR_TICK = "SUPERVISOR_TICK"
EVENT_CANDLES_SYNC_OK = "CANDLES_SYNC_OK"
EVENT_CANDLES_SYNC_ERROR = "CANDLES_SYNC_ERROR"
EVENT_SCHEDULER_STARTED = "SCHEDULER_STARTED"
EVENT_SCHEDULER_ERROR = "SCHEDULER_ERROR"


async def log_event(
    session: AsyncSession,
    level: str,
    module: str,
    event_type: str,
    message: str,
    context: dict[str, Any] | None = None,
    related_trade_id: int | None = None,
    related_signal_event_id: int | None = None,
) -> None:
    """Escribe un evento en bot_logs."""
    context_json = json.dumps(context, default=str) if context else None
    entry = BotLog(
        level=level,
        module=module,
        event_type=event_type,
        message=message,
        context_json=context_json,
        related_trade_id=related_trade_id,
        related_signal_event_id=related_signal_event_id,
    )
    session.add(entry)
