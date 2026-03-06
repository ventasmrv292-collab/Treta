"""Strategies API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.db import get_db
from app.models.strategy import Strategy
from app.schemas.strategy import StrategyResponse, StrategyCreate

router = APIRouter()


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(db=Depends(get_db)):
    result = await db.execute(select(Strategy).where(Strategy.active == True).order_by(Strategy.family, Strategy.name))
    return list(result.scalars().all())


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: int, db=Depends(get_db)):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


@router.post("", response_model=StrategyResponse)
async def create_strategy(payload: StrategyCreate, db=Depends(get_db)):
    strategy = Strategy(**payload.model_dump())
    db.add(strategy)
    await db.flush()
    await db.refresh(strategy)
    return strategy
