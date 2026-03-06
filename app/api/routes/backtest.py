"""Backtest API - run and list backtests."""
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.db import get_db
from app.models.backtest import BacktestRun, BacktestResult
from app.schemas.backtest import BacktestRunCreate, BacktestRunResponse
from app.services.market_data import MarketDataService
from app.services.fee_engine import FeeEngine, FeeProfile

router = APIRouter()


@router.post("", response_model=BacktestRunResponse)
async def run_backtest(payload: BacktestRunCreate, db=Depends(get_db)):
    """
    Run a simple backtest: fetch klines, simulate strategy with placeholder logic,
    compute PnL and store results.
    Placeholder: we just open/close on first/last candle for demo. Real strategies
    would use strategy_params and proper entry/exit rules.
    """
    run = BacktestRun(
        strategy_family=payload.strategy_family,
        strategy_name=payload.strategy_name,
        strategy_version=payload.strategy_version,
        symbol=payload.symbol,
        interval=payload.interval,
        start_time=payload.start_time,
        end_time=payload.end_time,
        initial_capital=payload.initial_capital,
        leverage=payload.leverage,
        fee_profile=payload.fee_profile,
        slippage_bps=payload.slippage_bps,
        params_json=payload.params_json,
        status="running",
    )
    db.add(run)
    await db.flush()

    try:
        svc = MarketDataService()
        start_ts = int(payload.start_time.timestamp() * 1000)
        end_ts = int(payload.end_time.timestamp() * 1000)
        klines = await svc.get_klines(
            symbol=payload.symbol,
            interval=payload.interval,
            limit=1500,
            start_time=start_ts,
            end_time=end_ts,
        )
        if len(klines) < 2:
            run.status = "completed"
            run.total_trades = 0
            run.net_pnl = Decimal("0")
            run.gross_pnl = Decimal("0")
            run.total_fees = Decimal("0")
            run.win_rate = 0
            run.profit_factor = 0
            await db.flush()
            await db.refresh(run)
            return run

        profile = FeeProfile.REALISTIC
        if payload.fee_profile == "conservative":
            profile = FeeProfile.CONSERVATIVE
        elif payload.fee_profile == "optimistic":
            profile = FeeProfile.OPTIMISTIC
        engine = FeeEngine.from_profile(profile, slippage_bps=payload.slippage_bps)

        # Placeholder: one trade from first candle open to last candle close
        first_ = klines[0]
        last_ = klines[-1]
        entry_price = first_["open"]
        exit_price = last_["close"]
        qty = (payload.initial_capital * payload.leverage) / entry_price  # notional = initial_capital * leverage
        qty = round(qty, 8)
        res = engine.compute_fees_and_pnl(
            quantity=qty,
            entry_price=entry_price,
            exit_price=exit_price,
            position_side="LONG",
            maker_taker_entry="TAKER",
            maker_taker_exit="TAKER",
            leverage=payload.leverage,
        )
        result_row = BacktestResult(
            run_id=run.id,
            trade_index=0,
            entry_time=first_["open_time"],
            exit_time=last_["open_time"],
            position_side="LONG",
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=qty,
            gross_pnl=res.gross_pnl_usdt,
            fees=res.entry_fee + res.exit_fee,
            net_pnl=res.net_pnl_usdt,
            exit_reason="backtest_end",
        )
        db.add(result_row)
        run.status = "completed"
        run.total_trades = 1
        run.net_pnl = res.net_pnl_usdt
        run.gross_pnl = res.gross_pnl_usdt
        run.total_fees = res.entry_fee + res.exit_fee
        run.win_rate = 100.0 if res.net_pnl_usdt > 0 else 0.0
        run.profit_factor = float(res.net_pnl_usdt / (res.entry_fee + res.exit_fee)) if (res.entry_fee + res.exit_fee) else 0
        run.max_drawdown_pct = 0
    except Exception as e:
        run.status = "failed"
        raise HTTPException(status_code=500, detail=str(e)) from e

    await db.flush()
    await db.refresh(run)
    return run


@router.get("", response_model=list[BacktestRunResponse])
async def list_backtests(
    db=Depends(get_db),
    limit: int = Query(50, le=100),
):
    result = await db.execute(
        select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
    )
    runs = list(result.scalars().all())
    return runs


@router.get("/{run_id}", response_model=BacktestRunResponse)
async def get_backtest(run_id: int, db=Depends(get_db)):
    result = await db.execute(select(BacktestRun).where(BacktestRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run
