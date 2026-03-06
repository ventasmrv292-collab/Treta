"""Webhook for n8n - receive automated trade signals."""
from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.models.trade import Trade
from app.schemas.trade import N8nTradeCreate, TradeResponse
from app.services.trade_service import n8n_create_to_trade

router = APIRouter()


@router.post("/n8n/trade", response_model=TradeResponse)
async def webhook_n8n_trade(payload: N8nTradeCreate, db=Depends(get_db)):
    """Receive a trade from n8n. Validates and stores as open position."""
    data = n8n_create_to_trade(payload)
    trade = Trade(**data)
    db.add(trade)
    await db.flush()
    await db.refresh(trade)
    return trade
