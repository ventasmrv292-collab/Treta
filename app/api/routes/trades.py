"""Trades API."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.trade import Trade
from app.schemas.trade import (
    TradeResponse,
    TradeListResponse,
    ManualTradeCreate,
    ManualTradeClose,
    TradeUpdate,
)
from app.services.trade_service import (
    manual_create_to_trade,
    close_trade_and_compute_pnl,
    get_default_fee_engine,
)

router = APIRouter()


@router.post("", response_model=TradeResponse)
async def create_manual_trade(
    payload: ManualTradeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a manual trade (open position)."""
    data = manual_create_to_trade(payload)
    trade = Trade(**data)
    db.add(trade)
    await db.flush()
    await db.refresh(trade)
    return trade


@router.get("", response_model=TradeListResponse)
async def list_trades(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    symbol: str | None = None,
    strategy_family: str | None = None,
    strategy_name: str | None = None,
    source: str | None = None,
    position_side: str | None = None,
    leverage: int | None = None,
    closed_only: bool | None = None,
    winners_only: bool | None = None,
    losers_only: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    """List trades with filters and pagination."""
    q = select(Trade)
    count_q = select(func.count()).select_from(Trade)

    if symbol:
        q = q.where(Trade.symbol == symbol)
        count_q = count_q.where(Trade.symbol == symbol)
    if strategy_family:
        q = q.where(Trade.strategy_family == strategy_family)
        count_q = count_q.where(Trade.strategy_family == strategy_family)
    if strategy_name:
        q = q.where(Trade.strategy_name == strategy_name)
        count_q = count_q.where(Trade.strategy_name == strategy_name)
    if source:
        q = q.where(Trade.source == source)
        count_q = count_q.where(Trade.source == source)
    if position_side:
        q = q.where(Trade.position_side == position_side.upper())
        count_q = count_q.where(Trade.position_side == position_side.upper())
    if leverage is not None:
        q = q.where(Trade.leverage == leverage)
        count_q = count_q.where(Trade.leverage == leverage)
    if closed_only:
        q = q.where(Trade.closed_at.isnot(None))
        count_q = count_q.where(Trade.closed_at.isnot(None))
    if winners_only:
        q = q.where(and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt > 0))
        count_q = count_q.where(and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt > 0))
    if losers_only:
        q = q.where(and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt < 0))
        count_q = count_q.where(and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt < 0))
    if date_from:
        q = q.where(Trade.created_at >= date_from)
        count_q = count_q.where(Trade.created_at >= date_from)
    if date_to:
        q = q.where(Trade.created_at <= date_to)
        count_q = count_q.where(Trade.created_at <= date_to)

    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(Trade.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = list(result.scalars().all())
    pages = (total + size - 1) // size if size else 0
    return TradeListResponse(items=items, total=total, page=page, size=size, pages=pages)


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single trade by id."""
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.patch("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: int,
    payload: ManualTradeClose,
    db: AsyncSession = Depends(get_db),
):
    """Close a trade with exit price and reason; computes fees and PnL."""
    trade = await close_trade_and_compute_pnl(db, trade_id, payload)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")
    await db.flush()
    await db.refresh(trade)
    return trade
