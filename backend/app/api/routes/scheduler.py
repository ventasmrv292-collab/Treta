"""Scheduler status API."""
from fastapi import APIRouter
from app.services.scheduler_service import get_scheduler_status

router = APIRouter()


@router.get("/status")
async def scheduler_status():
    """Estado del scheduler (última ejecución por job, errores)."""
    return get_scheduler_status()
