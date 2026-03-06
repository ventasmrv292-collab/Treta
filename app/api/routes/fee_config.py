"""Fee config API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.db import get_db
from app.models.fee_config import FeeConfig
from app.schemas.fee_config import FeeConfigResponse, FeeConfigUpdate

router = APIRouter()


@router.get("", response_model=list[FeeConfigResponse])
async def list_fee_configs(db=Depends(get_db)):
    result = await db.execute(select(FeeConfig).order_by(FeeConfig.name))
    return list(result.scalars().all())


@router.get("/default", response_model=FeeConfigResponse)
async def get_default_fee_config(db=Depends(get_db)):
    result = await db.execute(select(FeeConfig).where(FeeConfig.is_default == True).limit(1))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No default fee config")
    return row


@router.get("/{config_id}", response_model=FeeConfigResponse)
async def get_fee_config(config_id: int, db=Depends(get_db)):
    result = await db.execute(select(FeeConfig).where(FeeConfig.id == config_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Fee config not found")
    return row


@router.patch("/{config_id}", response_model=FeeConfigResponse)
async def update_fee_config(config_id: int, payload: FeeConfigUpdate, db=Depends(get_db)):
    result = await db.execute(select(FeeConfig).where(FeeConfig.id == config_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Fee config not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)
    return row
