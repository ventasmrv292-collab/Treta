"""Trade service - create, close, compute PnL."""
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.models.fee_config import FeeConfig
from app.models.paper_account import PaperAccount
from app.services.fee_engine import FeeEngine, FeeProfile
from app.services.trading_capital import (
    calc_entry_fee,
    calc_margin_used,
    get_fee_rate,
    validate_can_open_trade,
)
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
    """Convert ManualTradeCreate to Trade ORM kwargs (sin margen/fee; ver prepare_manual_trade para datos completos)."""
    out = {
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
    if getattr(d, "account_id", None) is not None:
        out["account_id"] = d.account_id
    if getattr(d, "fee_config_id", None) is not None:
        out["fee_config_id"] = d.fee_config_id
    return out


async def prepare_manual_trade(session: AsyncSession, payload: ManualTradeCreate) -> dict:
    """
    Prepara el diccionario para crear un trade: datos base + entry_notional, margin_used_usdt,
    entry_fee, capital_before_usdt. Valida margen si hay account_id.
    """
    data = manual_create_to_trade(payload)
    qty = Decimal(str(payload.quantity))
    entry_price = Decimal(str(payload.entry_price))
    entry_notional = (qty * entry_price).quantize(Decimal("0.0001"))
    margin_used = calc_margin_used(entry_notional, payload.leverage)

    engine = await get_default_fee_engine(session)
    maker_taker = (payload.maker_taker_entry or "TAKER").upper()
    rate = (
        engine.config.taker_rate()
        if maker_taker == "TAKER"
        else engine.config.maker_rate()
    )
    entry_fee = calc_entry_fee(entry_notional, rate)

    data["entry_notional"] = entry_notional
    data["margin_used_usdt"] = margin_used
    data["entry_fee"] = entry_fee

    account_id = getattr(payload, "account_id", None)
    if account_id is not None:
        result = await session.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        account = result.scalar_one_or_none()
        if account:
            data["capital_before_usdt"] = account.current_balance_usdt
            ok, msg = validate_can_open_trade(
                account.available_balance_usdt,
                margin_used,
                entry_fee,
            )
            if not ok:
                raise ValueError(msg)
    return data


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

    if trade.account_id is not None:
        await _update_account_on_trade_close(session, trade, res)

    return trade


async def _update_account_on_trade_close(
    session: AsyncSession, trade: Trade, res: "TradeFeesResult"
) -> None:
    """Actualiza la cuenta paper al cerrar una operación: libera margen, aplica PnL y fees."""
    result = await session.execute(
        select(PaperAccount).where(PaperAccount.id == trade.account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        return
    margin_used = trade.margin_used_usdt or Decimal("0")
    net_pnl = res.net_pnl_usdt
    total_fees_trade = res.entry_fee + res.exit_fee + (res.funding_fee or Decimal("0"))
    account.used_margin_usdt = max(Decimal("0"), account.used_margin_usdt - margin_used)
    account.current_balance_usdt = account.current_balance_usdt + net_pnl
    account.realized_pnl_usdt = account.realized_pnl_usdt + net_pnl
    account.total_fees_usdt = account.total_fees_usdt + total_fees_trade
    account.unrealized_pnl_usdt = Decimal("0")
    account.available_balance_usdt = account.current_balance_usdt - account.used_margin_usdt
    trade.capital_after_usdt = account.current_balance_usdt
