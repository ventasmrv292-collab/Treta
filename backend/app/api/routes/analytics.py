"""Analytics and dashboard metrics."""
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from fastapi import Query
from app.db import get_db
from app.models.trade import Trade
from app.services.analytics_service import get_runtime_recommendations
from app.models.paper_account import PaperAccount
from app.schemas.analytics import DashboardMetrics, StrategyComparison, StrategyVersionComparison, LeverageComparison
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

    # PnL by strategy (incl. version para v1 vs v2)
    by_strategy = await db.execute(
        select(Trade.strategy_name, Trade.strategy_family, Trade.strategy_version, func.sum(Trade.net_pnl_usdt).label("net_pnl"))
        .where(closed)
        .group_by(Trade.strategy_name, Trade.strategy_family, Trade.strategy_version)
    )
    pnl_by_strategy = [
        {"strategy_name": r[0], "strategy_family": r[1], "strategy_version": r[2] or "1.0.0", "net_pnl": float(r[3] or 0)}
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
            Trade.strategy_version,
            func.count(Trade.id).label("total_trades"),
            func.sum(Trade.net_pnl_usdt).label("net_pnl"),
            func.sum(Trade.gross_pnl_usdt).label("gross_pnl"),
            (func.coalesce(func.sum(Trade.entry_fee), 0) + func.coalesce(func.sum(Trade.exit_fee), 0)).label("fees"),
        )
        .where(closed)
        .group_by(Trade.strategy_name, Trade.strategy_family, Trade.strategy_version)
    )
    result = await db.execute(q)
    rows = result.all()
    out = []
    for r in rows:
        strat_name, strat_family, strat_ver, total, net, gross, fees = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        wins = await db.execute(
            select(func.count(Trade.id), func.avg(Trade.net_pnl_usdt)).where(
                closed, Trade.strategy_name == strat_name, Trade.strategy_version == strat_ver, Trade.net_pnl_usdt > 0
            )
        )
        loss = await db.execute(
            select(func.count(Trade.id), func.avg(Trade.net_pnl_usdt)).where(
                closed, Trade.strategy_name == strat_name, Trade.strategy_version == strat_ver, Trade.net_pnl_usdt < 0
            )
        )
        wrow = wins.one_or_none()
        lrow = loss.one_or_none()
        wc = int(wrow[0]) if wrow else 0
        wa = wrow[1] if wrow else None
        lc = int(lrow[0]) if lrow else 0
        la = lrow[1] if lrow else None
        total = total or 0
        win_rate = (wc / total * 100) if total else 0
        gross = _decimal_or_zero(gross)
        fees = _decimal_or_zero(fees)
        net = _decimal_or_zero(net)
        losses_sum = await db.execute(
            select(func.sum(Trade.net_pnl_usdt)).where(closed, Trade.strategy_name == strat_name, Trade.strategy_version == strat_ver, Trade.net_pnl_usdt < 0)
        )
        wins_sum = await db.execute(
            select(func.sum(Trade.net_pnl_usdt)).where(closed, Trade.strategy_name == strat_name, Trade.strategy_version == strat_ver, Trade.net_pnl_usdt > 0)
        )
        ls = abs(_decimal_or_zero(losses_sum.scalar()))
        ws = _decimal_or_zero(wins_sum.scalar())
        pf = float(ws / ls) if ls else 0
        avg_win = _decimal_or_zero(wa)
        avg_loss = _decimal_or_zero(la) if la else Decimal("0")
        expectancy = (avg_win * (wc / total) + avg_loss * (lc / total)) if total else Decimal("0")
        out.append(
            StrategyComparison(
                strategy_name=strat_name,
                strategy_family=strat_family,
                strategy_version=strat_ver or "1.0.0",
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
        select(Trade.strategy_name, Trade.strategy_family, Trade.strategy_version, func.sum(Trade.net_pnl_usdt).label("net_pnl"))
        .where(closed).group_by(Trade.strategy_name, Trade.strategy_family, Trade.strategy_version)
    )
    pnl_by_strategy = [{"strategy_name": r[0], "strategy_family": r[1], "strategy_version": r[2] or "1.0.0", "net_pnl": float(r[3] or 0)} for r in by_strategy.all()]
    by_lev = await db.execute(
        select(Trade.leverage, func.sum(Trade.net_pnl_usdt).label("net_pnl")).where(closed).group_by(Trade.leverage)
    )
    pnl_by_leverage = [{"leverage": r[0], "net_pnl": float(r[1] or 0)} for r in by_lev.all()]

    account = None
    equity_usdt = None
    open_positions_count = 0
    if account_id:
        acc_result = await db.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        acc = acc_result.scalar_one_or_none()
        if acc:
            account = PaperAccountResponse.model_validate(acc)
            equity_usdt = str(acc.current_balance_usdt + acc.unrealized_pnl_usdt)
        open_count = await db.execute(
            select(func.count(Trade.id)).where(
                Trade.account_id == account_id,
                Trade.closed_at.is_(None),
            )
        )
        open_positions_count = open_count.scalar() or 0

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
        open_positions_count=int(open_positions_count),
    )


@router.get("/by-strategy-version", response_model=list[StrategyVersionComparison])
async def get_by_strategy_version(db: AsyncSession = Depends(get_db)):
    """Comparativa v1 vs v2 por strategy_name, strategy_version, timeframe, side; FASE 1: payoff_ratio, avg_expected_net_rr_at_open."""
    closed = and_(Trade.closed_at.isnot(None), Trade.net_pnl_usdt.isnot(None))
    q = (
        select(
            Trade.strategy_family,
            Trade.strategy_name,
            Trade.strategy_version,
            Trade.timeframe,
            Trade.position_side,
            func.count(Trade.id).label("total_trades"),
            func.coalesce(func.sum(Trade.gross_pnl_usdt), 0).label("gross_pnl"),
            func.coalesce(func.sum(Trade.net_pnl_usdt), 0).label("net_pnl"),
            (func.coalesce(func.sum(Trade.entry_fee), 0) + func.coalesce(func.sum(Trade.exit_fee), 0)).label("total_fees"),
            func.coalesce(func.sum(Trade.slippage_usdt), 0).label("total_slippage_usdt"),
            func.avg(Trade.slippage_usdt).label("avg_slippage_usdt"),
            func.sum(case([(Trade.net_pnl_usdt > 0, 1)], else_=0)).label("wins"),
            func.avg(Trade.net_pnl_usdt).label("avg_pnl"),
            func.avg(case([(Trade.net_pnl_usdt > 0, Trade.gross_pnl_usdt)], else_=None)).label("avg_gross_win"),
            func.avg(case([(Trade.net_pnl_usdt < 0, Trade.gross_pnl_usdt)], else_=None)).label("avg_gross_loss"),
            func.avg(Trade.expected_net_rr_at_open).label("avg_expected_net_rr_at_open"),
        )
        .where(closed)
        .group_by(Trade.strategy_family, Trade.strategy_name, Trade.strategy_version, Trade.timeframe, Trade.position_side)
    )
    result = await db.execute(q)
    rows = result.all()
    out = []
    for r in rows:
        total = int(r[5] or 0)
        wins = int(r[11] or 0)
        win_rate = (wins / total * 100) if total else 0.0
        gross = _decimal_or_zero(r[6])
        net = _decimal_or_zero(r[7])
        fees = _decimal_or_zero(r[8])
        total_slip = _decimal_or_zero(r[9])
        avg_slip = _decimal_or_zero(r[10])
        avg_pnl = _decimal_or_zero(r[12])
        avg_gross_win = _decimal_or_zero(r[13]) if r[13] is not None else None
        avg_gross_loss = _decimal_or_zero(r[14]) if r[14] is not None else None
        avg_expected_net_rr = _decimal_or_zero(r[15]) if r[15] is not None else None
        avg_win = avg_pnl if wins else Decimal("0")
        losses_sum_q = await db.execute(
            select(func.sum(Trade.net_pnl_usdt)).where(
                closed,
                Trade.strategy_family == r[0],
                Trade.strategy_name == r[1],
                Trade.strategy_version == r[2],
                Trade.timeframe == r[3],
                Trade.position_side == r[4],
                Trade.net_pnl_usdt < 0,
            )
        )
        wins_sum_q = await db.execute(
            select(func.sum(Trade.net_pnl_usdt)).where(
                closed,
                Trade.strategy_family == r[0],
                Trade.strategy_name == r[1],
                Trade.strategy_version == r[2],
                Trade.timeframe == r[3],
                Trade.position_side == r[4],
                Trade.net_pnl_usdt > 0,
            )
        )
        ls = abs(_decimal_or_zero(losses_sum_q.scalar()))
        ws = _decimal_or_zero(wins_sum_q.scalar())
        pf = float(ws / ls) if ls else 0.0
        avg_loss_q = await db.execute(
            select(func.avg(Trade.net_pnl_usdt)).where(
                closed,
                Trade.strategy_family == r[0],
                Trade.strategy_name == r[1],
                Trade.strategy_version == r[2],
                Trade.timeframe == r[3],
                Trade.position_side == r[4],
                Trade.net_pnl_usdt < 0,
            )
        )
        avg_win_q = await db.execute(
            select(func.avg(Trade.net_pnl_usdt)).where(
                closed,
                Trade.strategy_family == r[0],
                Trade.strategy_name == r[1],
                Trade.strategy_version == r[2],
                Trade.timeframe == r[3],
                Trade.position_side == r[4],
                Trade.net_pnl_usdt > 0,
            )
        )
        avg_win = _decimal_or_zero(avg_win_q.scalar())
        avg_loss = _decimal_or_zero(avg_loss_q.scalar())
        payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss and avg_loss != 0 else None
        avg_fees = (fees / total) if total else None
        out.append(
            StrategyVersionComparison(
                strategy_family=r[0],
                strategy_name=r[1],
                strategy_version=r[2] or "1.0.0",
                timeframe=r[3] or "",
                position_side=r[4] or "LONG",
                total_trades=total,
                closed_trades=total,
                gross_pnl=gross,
                net_pnl=net,
                total_fees=fees,
                total_slippage_usdt=total_slip,
                avg_slippage_usdt=avg_slip,
                win_rate=round(win_rate, 2),
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=round(pf, 4),
                avg_gross_win=avg_gross_win,
                avg_gross_loss=avg_gross_loss,
                avg_fees=avg_fees,
                expectancy=avg_pnl,
                payoff_ratio=payoff_ratio,
                avg_expected_net_rr_at_open=avg_expected_net_rr,
            )
        )
    return out


@router.get("/runtime-recommendations")
async def runtime_recommendations(
    days: int = Query(7, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
):
    """Diagnóstico y recomendaciones según rendimiento reciente (estrategia, timeframe, LONG vs SHORT)."""
    return await get_runtime_recommendations(db, days=days)
