"""Webhook for n8n - receive automated trade signals."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.models.trade import Trade
from app.schemas.trade import N8nTradeCreate, TradeResponse
from app.services.trade_service import n8n_create_to_trade, prepare_n8n_trade
from app.services.pushover_service import send_trade_opened
from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_WEBHOOK,
    EVENT_SIGNAL_RECEIVED,
    EVENT_SIGNAL_REJECTED,
    EVENT_TRADE_OPENED,
    EVENT_DUPLICATE_SIGNAL,
    EVENT_RISK_LIMIT_BLOCK,
)

router = APIRouter()


@router.post("/n8n/trade", response_model=TradeResponse)
async def webhook_n8n_trade(payload: N8nTradeCreate, db=Depends(get_db)):
    """Receive a trade from n8n. Validates (idempotency, account, risk) and stores as open position."""
    try:
        data_override = await prepare_n8n_trade(db, payload)
    except ValueError as e:
        msg = str(e)
        if msg == "DUPLICATE_SIGNAL":
            await bot_log_event(
                db, "WARN", MODULE_WEBHOOK, EVENT_DUPLICATE_SIGNAL,
                f"Señal duplicada rechazada: {getattr(payload, 'idempotency_key', '')}",
                context={"idempotency_key": getattr(payload, "idempotency_key", None)},
            )
            await db.commit()
            raise HTTPException(status_code=409, detail="Señal duplicada (idempotency_key)")
        if msg.startswith("RISK_LIMIT_BLOCK:"):
            await bot_log_event(
                db, "WARN", MODULE_WEBHOOK, EVENT_RISK_LIMIT_BLOCK,
                msg,
                context={"symbol": payload.symbol},
            )
            await db.commit()
            raise HTTPException(status_code=400, detail=msg.replace("RISK_LIMIT_BLOCK:", ""))
        await bot_log_event(
            db, "WARN", MODULE_WEBHOOK, EVENT_SIGNAL_REJECTED,
            msg,
            context={"symbol": payload.symbol},
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=msg)

    data = n8n_create_to_trade(payload, data_override)
    trade = Trade(**data)
    db.add(trade)
    await db.flush()
    await db.refresh(trade)
    await bot_log_event(
        db, "INFO", MODULE_WEBHOOK, EVENT_SIGNAL_RECEIVED,
        f"Señal n8n recibida → Trade #{trade.id}",
        context={"symbol": payload.symbol, "trade_id": trade.id},
        related_trade_id=trade.id,
    )
    await bot_log_event(
        db, "INFO", MODULE_WEBHOOK, EVENT_TRADE_OPENED,
        f"Trade #{trade.id} abierto desde n8n: {trade.symbol} {trade.position_side}",
        context={"symbol": trade.symbol, "position_side": trade.position_side},
        related_trade_id=trade.id,
    )
    asyncio.create_task(send_trade_opened(trade))
    return trade
