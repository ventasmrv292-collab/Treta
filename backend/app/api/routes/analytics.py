"""Analytics and dashboard metrics."""
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.db import get_db
from app.models.trade import Trade
from app.models.paper_account import PaperAccount
from app.schemas.analytics import DashboardMetrics, StrategyComparison, LeverageComparison
from app.schemas.paper_account import DashboardSummaryResponse, PaperAccountResponse

router = APIRouter()


def _decimal_or_zero(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """Aggregate metrics for dashboard: total trades, win rate, PnL, fees, by strategy, by leverage."""
    # Only closed trades
    closed = and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt.isnot(None))

    total_result = await db.execute(
        select(func.count(Trade.id)).where(closed)
    )
    total_trades = total_result.scalar() or 0

    winners_result = await db.execute(
        select(func.count(Trade.id)).where(closed, Trade.net_pnl_usdt > 0)
    )
    winning_trades = winners_result.scalar() or 0
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades else 0.0

    gross_result = await db.execute(select(func.coalesce(func.sum(Trade.gross_pnl_usdt), 0)).where(closed))
    net_result = await db.execute(select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(closed))
    fees_result = await db.execute(
        select(
            func.coalesce(func.sum(Trade.entry_fee), 0) + func.coalesce(func.sum(Trade.exit_fee), 0)
            + func.coalesce(func.sum(Trade.funding_fee), 0)
        ).where(closed)
    )
    gross_pnl = _decimal_or_zero(gross_result.scalar())
    net_pnl = _decimal_or_zero(net_result.scalar())
    total_fees = _decimal_or_zero(fees_result.scalar())

    # Profit factor: sum(wins) / abs(sum(losses))
    wins_sum = await db.execute(select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(closed, Trade.net_pnl_usdt > 0))
    losses_sum = await db.execute(select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(closed, Trade.net_pnl_usdt < 0))
    wins_total = _decimal_or_zero(wins_sum.scalar())
    losses_total = abs(_decimal_or_zero(losses_sum.scalar()))
    profit_factor = float(wins_total / losses_total) if losses_total else (float(wins_total) if wins_total else 0.0)

    # PnL by strategy
    by_strategy = await db.execute(
        select(Trade.strategy_name, Trade.strategy_family, func.sum(Trade.net_pnl_usdt).label("net_pnl"))
        .where(closed)
        .group_by(Trade.strategy_name, Trade.strategy_family)
    )
    pnl_by_strategy = [
        {"strategy_name": r[0], "strategy_family": r[1], "net_pnl": float(r[2] or 0)}
        for r in by_strategy.all()
    ]

    # PnL by leverage
    by_lev = await db.execute(
        select(Trade.leverage, func.sum(Trade.net_pnl_usdt).label("net_pnl")).where(closed).group_by(Trade.leverage)
    )
    pnl_by_leverage = [{"leverage": r[0], "net_pnl": float(r[1] or 0)} for r in by_lev.all()]

    return DashboardMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=round(win_rate, 2),
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        total_fees=total_fees,
        profit_factor=round(profit_factor, 4),
        pnl_by_strategy=pnl_by_strategy,
        pnl_by_leverage=pnl_by_leverage,
    )


@router.get("/by-strategy", response_model=list[StrategyComparison])
async def get_by_strategy(db: AsyncSession = Depends(get_db)):
    """Compare performance by strategy."""
    closed = and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt.isnot(None))
    q = (
        select(
            Trade.strategy_name,
            Trade.strategy_family,
            func.count(Trade.id).label("total_trades"),
            func.sum(Trade.net_pnl_usdt).label("net_pnl"),
            func.sum(Trade.gross_pnl_usdt).label("gross_pnl"),
            (func.coalesce(func.sum(Trade.entry_fee), 0) + func.coalesce(func.sum(Trade.exit_fee), 0)).label("fees"),
        )
        .where(closed)
        .group_by(Trade.strategy_name, Trade.strategy_family)
    )
    result = await db.execute(q)
    rows = result.all()
    out = []
    for r in rows:
        wins = await db.execute(
            select(func.count(Trade.id), func.avg(Trade.net_pnl_usdt)).where(
                closed, Trade.strategy_name == r[0], Trade.net_pnl_usdt > 0
            )
        )
        loss = await db.execute(
            select(func.count(Trade.id), func.avg(Trade.net_pnl_usdt)).where(
                closed, Trade.strategy_name == r[0], Trade.net_pnl_usdt < 0
            )
        )
        wrow = wins.one_or_none()
        lrow = loss.one_or_none()
        wc = int(wrow[0]) if wrow else 0
        wa = wrow[1] if wrow else None
        lc = int(lrow[0]) if lrow else 0
        la = lrow[1] if lrow else None
        total = r[2] or 0
        win_rate = (wc / total * 100) if total else 0
        gross = _decimal_or_zero(r[4])
        fees = _decimal_or_zero(r[5])
        net = _decimal_or_zero(r[3])
        losses_sum = await db.execute(
            select(func.sum(Trade.net_pnl_usdt)).where(closed, Trade.strategy_name == r[0], Trade.net_pnl_usdt < 0)
        )
        wins_sum = await db.execute(
            select(func.sum(Trade.net_pnl_usdt)).where(closed, Trade.strategy_name == r[0], Trade.net_pnl_usdt > 0)
        )
        ls = abs(_decimal_or_zero(losses_sum.scalar()))
        ws = _decimal_or_zero(wins_sum.scalar())
        pf = float(ws / ls) if ls else 0
        avg_win = _decimal_or_zero(wa)
        avg_loss = _decimal_or_zero(la) if la else Decimal("0")
        expectancy = (avg_win * (wc / total) + avg_loss * (lc / total)) if total else Decimal("0")
        out.append(
            StrategyComparison(
                strategy_name=r[0],
                strategy_family=r[1],
                total_trades=total,
                net_pnl=net,
                gross_pnl=gross,
                total_fees=fees,
                win_rate=round(win_rate, 2),
                profit_factor=round(pf, 4),
                avg_win=avg_win,
                avg_loss=avg_loss,
                expectancy=expectancy,
            )
        )
    return out


@router.get("/by-leverage", response_model=list[LeverageComparison])
async def get_by_leverage(db: AsyncSession = Depends(get_db)):
    """Compare performance by leverage (e.g. x10 vs x20)."""
    closed = and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt.isnot(None))
    q = (
        select(
            Trade.leverage,
            func.count(Trade.id).label("total_trades"),
            func.sum(Trade.net_pnl_usdt).label("net_pnl"),
            (func.coalesce(func.sum(Trade.entry_fee), 0) + func.coalesce(func.sum(Trade.exit_fee), 0)).label("fees"),
        )
        .where(closed)
        .group_by(Trade.leverage)
    )
    result = await db.execute(q)
    rows = result.all()
    out = []
    for r in rows:
        wins = await db.execute(
            select(func.count(Trade.id)).where(closed, Trade.leverage == r[0], Trade.net_pnl_usdt > 0)
        )
        w = wins.scalar() or 0
        total = r[1] or 0
        win_rate = (w / total * 100) if total else 0
        out.append(
            LeverageComparison(
                leverage=r[0],
                total_trades=total,
                net_pnl=_decimal_or_zero(r[2]),
                win_rate=round(win_rate, 2),
                total_fees=_decimal_or_zero(r[3]),
            )
        )
    return out


@router.get("/equity-curve")
async def get_equity_curve(
    db: AsyncSession = Depends(get_db),
    period: str = Query("all", description="day, week, month, all"),
):
    """Cumulative net PnL over time (for equity curve chart)."""
    closed = and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt.isnot(None))
    q = select(Trade.closed_at, Trade.net_pnl_usdt).where(closed).order_by(Trade.closed_at)
    result = await db.execute(q)
    rows = result.all()
    if not rows:
        return {"points": []}
    now = datetime.utcnow()
    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(weeks=1)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        start = None
    points = []
    cum = Decimal("0")
    for r in rows:
        if start and r[0] and r[0].replace(tzinfo=None) < start.replace(tzinfo=None) if hasattr(start, "replace") else False:
            continue
        cum += _decimal_or_zero(r[1])
        points.append({"time": r[0].isoformat() if r[0] else None, "equity": float(cum)})
    return {"points": points}


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    account_id: int | None = Query(None, description="ID cuenta paper para incluir capital"),
):
    """Resumen completo: métricas de trades + cuenta paper (si account_id) + precio BTC opcional."""
    # Reutilizar lógica del dashboard existente
    closed = and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt.isnot(None))
    total_result = await db.execute(select(func.count(Trade.id)).where(closed))
    total_trades = total_result.scalar() or 0
    winners_result = await db.execute(select(func.count(Trade.id)).where(closed, Trade.net_pnl_usdt > 0))
    winning_trades = winners_result.scalar() or 0
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades else 0.0
    net_result = await db.execute(select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(closed))
    gross_result = await db.execute(select(func.coalesce(func.sum(Trade.gross_pnl_usdt), 0)).where(closed))
    fees_result = await db.execute(
        select(
            func.coalesce(func.sum(Trade.entry_fee), 0) + func.coalesce(func.sum(Trade.exit_fee), 0)
            + func.coalesce(func.sum(Trade.funding_fee), 0)
        ).where(closed)
    )
    net_pnl = _decimal_or_zero(net_result.scalar())
    gross_pnl = _decimal_or_zero(gross_result.scalar())
    total_fees = _decimal_or_zero(fees_result.scalar())
    wins_sum = await db.execute(select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(closed, Trade.net_pnl_usdt > 0))
    losses_sum = await db.execute(select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(closed, Trade.net_pnl_usdt < 0))
    wins_total = _decimal_or_zero(wins_sum.scalar())
    losses_total = abs(_decimal_or_zero(losses_sum.scalar()))
    profit_factor = float(wins_total / losses_total) if losses_total else (float(wins_total) if wins_total else 0.0)
    by_strategy = await db.execute(
        select(Trade.strategy_name, Trade.strategy_family, func.sum(Trade.net_pnl_usdt).label("net_pnl"))
        .where(closed).group_by(Trade.strategy_name, Trade.strategy_family)
    )
    pnl_by_strategy = [{"strategy_name": r[0], "strategy_family": r[1], "net_pnl": float(r[2] or 0)} for r in by_strategy.all()]
    by_lev = await db.execute(
        select(Trade.leverage, func.sum(Trade.net_pnl_usdt).label("net_pnl")).where(closed).group_by(Trade.leverage)
    )
    pnl_by_leverage = [{"leverage": r[0], "net_pnl": float(r[1] or 0)} for r in by_lev.all()]

    account = None
    equity_usdt = None
    if account_id:
        acc_result = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        acc = acc_result.scalar_one_or_none()
        if acc:
            account = PaperAccountResponse.model_validate(acc)
            equity_usdt = str(acc.current_balance_usdt + acc.unrealized_pnl_usdt)

    return DashboardSummaryResponse(
        total_trades=total_trades,
        win_rate=round(win_rate, 2),
        net_pnl=str(net_pnl),
        gross_pnl=str(gross_pnl),
        total_fees=str(total_fees),
        profit_factor=round(profit_factor, 4),
        pnl_by_strategy=pnl_by_strategy,
        pnl_by_leverage=pnl_by_leverage,
        account=account,
        equity_usdt=equity_usdt,
    )
