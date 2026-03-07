"""Dashboard summary API - alias y agregación para la web."""
from fastapi import APIRouter, Depends, Query
from app.db import get_db
from app.api.routes.analytics import get_dashboard_summary
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    account_id: int | None = Query(None, description="ID cuenta paper"),
):
    """Resumen del dashboard: métricas + cuenta (si account_id). Redirige a analytics/dashboard-summary."""
    return await get_dashboard_summary(db=db, account_id=account_id)
