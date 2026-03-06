"""Trade service - create, close, compute PnL."""
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.models.fee_config import FeeConfig
from app.services.fee_engine import FeeEngine, FeeProfile
from app.schemas.trade import ManualTradeCreate, ManualTradeClose, N8nTradeCreate


async def get_default_fee_engine(session: AsyncSession) -> FeeEngine:
    """Load default fee config from DB or use realistic profile."""
    result = await session.execute(
        select(FeeConfig).where(FeeConfig.is_default == True).limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        return FeeEngine(
            maker_fee_bps=float(row.maker_fee_bps),
            taker_fee_bps=float(row.taker_fee_bps),
            bnb_discount_pct=float(row.bnb_discount_pct),
            default_slippage_bps=float(row.default_slippage_bps),
            include_funding=row.include_funding,
        )
    return FeeEngine.from_profile(FeeProfile.REALISTIC)


def manual_create_to_trade(d: ManualTradeCreate) -> dict:
    """Convert ManualTradeCreate to Trade ORM kwargs."""
    return {
        "source": d.source,
        "symbol": d.symbol,
        "market": d.market,
        "strategy_family": d.strategy_family,
        "strategy_name": d.strategy_name,
        "strategy_version": d.strategy_version,
        "timeframe": d.timeframe,
        "position_side": d.position_side,
        "order_side_entry": d.order_side_entry,
        "order_type_entry": d.order_type_entry,
        "maker_taker_entry": d.maker_taker_entry,
        "leverage": d.leverage,
        "quantity": d.quantity,
        "entry_price": d.entry_price,
        "take_profit": d.take_profit,
        "stop_loss": d.stop_loss,
        "notes": d.notes,
    }


def n8n_create_to_trade(d: N8nTradeCreate) -> dict:
    """Convert N8nTradeCreate to Trade ORM kwargs."""
    return {
        "source": d.source,
        "symbol": d.symbol,
        "market": d.market,
        "strategy_family": d.strategy_family,
        "strategy_name": d.strategy_name,
        "strategy_version": d.strategy_version,
        "timeframe": d.timeframe,
        "position_side": d.position_side,
        "order_side_entry": "BUY" if d.position_side == "LONG" else "SELL",
        "order_type_entry": d.entry_order_type,
        "maker_taker_entry": d.maker_taker_entry,
        "leverage": d.leverage,
        "quantity": d.quantity,
        "entry_price": d.entry_price,
        "take_profit": d.take_profit,
        "stop_loss": d.stop_loss,
        "signal_timestamp": d.signal_timestamp,
        "strategy_params_json": d.strategy_params_json,
        "notes": d.notes,
    }


async def close_trade_and_compute_pnl(
    session: AsyncSession,
    trade_id: int,
    payload: ManualTradeClose,
) -> Trade | None:
    """Set exit fields and compute fees/PnL, then return updated trade."""
    result = await session.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade or trade.closed_at:
        return None

    engine = await get_default_fee_engine(session)
    closed_at = payload.closed_at or datetime.now(timezone.utc)
    res = engine.compute_fees_and_pnl(
        quantity=trade.quantity,
        entry_price=trade.entry_price,
        exit_price=payload.exit_price,
        position_side=trade.position_side,
        maker_taker_entry=trade.maker_taker_entry or "TAKER",
        maker_taker_exit=payload.maker_taker_exit,
        leverage=trade.leverage,
    )

    trade.exit_price = payload.exit_price
    trade.exit_order_type = payload.exit_order_type
    trade.maker_taker_exit = payload.maker_taker_exit
    trade.exit_reason = payload.exit_reason
    trade.closed_at = closed_at
    trade.entry_notional = res.entry_notional
    trade.exit_notional = res.exit_notional
    trade.entry_fee = res.entry_fee
    trade.exit_fee = res.exit_fee
    trade.funding_fee = res.funding_fee
    trade.slippage_usdt = res.slippage_usdt
    trade.gross_pnl_usdt = res.gross_pnl_usdt
    trade.net_pnl_usdt = res.net_pnl_usdt
    trade.pnl_pct_notional = res.pnl_pct_notional
    trade.pnl_pct_margin = res.pnl_pct_margin
    return trade
