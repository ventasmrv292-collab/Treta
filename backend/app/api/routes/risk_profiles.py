"""Risk profiles and position sizing preview API."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.risk_profile import RiskProfile
from app.models.paper_account import PaperAccount
from app.schemas.risk_profile import RiskProfileResponse, PositionSizePreviewResponse
from app.services.risk_management import (
    calc_position_size_by_fixed_qty,
    calc_position_size_by_fixed_notional,
    calc_position_size_by_risk_pct,
    SIZING_FIXED_QTY,
    SIZING_FIXED_NOTIONAL,
    SIZING_RISK_PCT,
)
from app.services.trading_capital import calc_margin_used, calc_entry_fee
from app.services.trade_service import get_default_fee_engine

router = APIRouter()


@router.get("", response_model=list[RiskProfileResponse])
async def list_risk_profiles(db: AsyncSession = Depends(get_db)):
    """Lista todos los risk profiles."""
    result = await db.execute(select(RiskProfile).order_by(RiskProfile.name))
    return list(result.scalars().all())


@router.get("/{profile_id}", response_model=RiskProfileResponse)
async def get_risk_profile(profile_id: int, db: AsyncSession = Depends(get_db)):
    """Obtiene un risk profile por id."""
    r = await db.execute(select(RiskProfile).where(RiskProfile.id == profile_id))
    profile = r.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Risk profile not found")
    return profile


@router.get("/{profile_id}/position-size-preview", response_model=PositionSizePreviewResponse)
async def position_size_preview(
    profile_id: int,
    entry_price: Decimal = Query(..., description="Precio de entrada"),
    leverage: int = Query(10, ge=1, le=125),
    stop_loss: Decimal | None = Query(None),
    position_side: str = Query("LONG"),
    account_id: int | None = Query(None, description="Opcional, para equity en RISK_PCT"),
    db: AsyncSession = Depends(get_db),
):
    """
    Preview de quantity, notional, margen, fee y pérdida estimada hasta SL según el risk profile.
    """
    r = await db.execute(select(RiskProfile).where(RiskProfile.id == profile_id))
    profile = r.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Risk profile not found")

    equity = Decimal("0")
    if account_id:
        acc = (await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))).scalar_one_or_none()
        if acc:
            equity = (acc.current_balance_usdt or 0) + (acc.unrealized_pnl_usdt or 0)

    qty: Decimal
    if profile.sizing_mode == SIZING_FIXED_QTY and profile.fixed_quantity:
        qty = calc_position_size_by_fixed_qty(profile.fixed_quantity)
    elif profile.sizing_mode == SIZING_FIXED_NOTIONAL and profile.fixed_notional_usdt:
        qty = calc_position_size_by_fixed_notional(profile.fixed_notional_usdt, entry_price)
    elif profile.sizing_mode == SIZING_RISK_PCT and profile.risk_pct_per_trade and stop_loss:
        qty = calc_position_size_by_risk_pct(
            entry_price, stop_loss, equity, profile.risk_pct_per_trade, position_side
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Profile requiere fixed_quantity, fixed_notional_usdt o risk_pct_per_trade+stop_loss",
        )

    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity calculada es 0")

    entry_notional = (qty * entry_price).quantize(Decimal("0.0001"))
    margin_used = calc_margin_used(entry_notional, leverage)
    engine = await get_default_fee_engine(db)
    rate = engine.config.taker_rate()
    entry_fee_estimate = calc_entry_fee(entry_notional, rate)

    estimated_loss_to_sl: Decimal | None = None
    if stop_loss and stop_loss > 0:
        if position_side.upper() == "LONG":
            estimated_loss_to_sl = ((entry_price - stop_loss) * qty).quantize(Decimal("0.0001"))
        else:
            estimated_loss_to_sl = ((stop_loss - entry_price) * qty).quantize(Decimal("0.0001"))

    return PositionSizePreviewResponse(
        quantity=qty,
        entry_notional=entry_notional,
        margin_used_usdt=margin_used,
        entry_fee_estimate=entry_fee_estimate,
        estimated_loss_to_sl_usdt=estimated_loss_to_sl,
    )
