"""Paper accounts API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.paper_account import PaperAccount
from app.schemas.paper_account import PaperAccountResponse

router = APIRouter()


@router.get("", response_model=list[PaperAccountResponse])
async def list_paper_accounts(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, description="ACTIVE, CLOSED"),
):
    """Lista cuentas paper."""
    q = select(PaperAccount)
    if status:
        q = q.where(PaperAccount.status == status)
    q = q.order_by(PaperAccount.id)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{account_id}", response_model=PaperAccountResponse)
async def get_paper_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Obtiene una cuenta paper por id."""
    result = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
    acc = result.scalar_one_or_none()
    if not acc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return acc
