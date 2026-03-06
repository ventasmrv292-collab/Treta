"""Supervisor status API."""
from fastapi import APIRouter
from app.services.position_supervisor import get_supervisor_status

router = APIRouter()


@router.get("/status")
async def supervisor_status():
    """Estado del supervisor de posiciones (actualiza PnL no realizado y TP/SL)."""
    return get_supervisor_status()
