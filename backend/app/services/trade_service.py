"""Trade service - create, close, compute PnL."""
from decimal import Decimal
from datetime import datetime, timezone, date

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.models.fee_config import FeeConfig
from app.models.paper_account import PaperAccount
from app.models.risk_profile import RiskProfile
from app.services.fee_engine import FeeEngine, FeeProfile
from app.services.trading_capital import (
    calc_entry_fee,
    calc_margin_used,
    validate_can_open_trade,
)
from app.services.risk_management import (
    validate_risk_limits,
    calc_position_size_by_fixed_qty,
    calc_position_size_by_fixed_notional,
    calc_position_size_by_risk_pct,
    SIZING_FIXED_QTY,
    SIZING_FIXED_NOTIONAL,
    SIZING_RISK_PCT,
)
from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_TRADE,
    EVENT_TRADE_OPENED,
    EVENT_TRADE_CLOSED,
    EVENT_RISK_LIMIT_BLOCK,
    EVENT_DUPLICATE_SIGNAL,
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
    if getattr(d, "risk_profile_id", None) is not None:
        out["risk_profile_id"] = d.risk_profile_id
    return out


async def _get_risk_context(session: AsyncSession, account_id: int) -> tuple[int, Decimal, int]:
    """(open_positions_count, daily_realized_pnl, consecutive_losses)."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    open_count = (
        await session.execute(
            select(func.count()).select_from(Trade).where(
                Trade.account_id == account_id,
                Trade.closed_at.is_(None),
            )
        )
    ).scalar() or 0
    daily_pnl_result = (
        await session.execute(
            select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(
                Trade.account_id == account_id,
                Trade.closed_at.isnot(None),
                Trade.closed_at >= today_start,
            )
        )
    ).scalar()
    daily_pnl = Decimal(str(daily_pnl_result or 0))
    # Consecutive losses: simplified, count last closed trades that are losses
    last_closed = (
        await session.execute(
            select(Trade)
            .where(Trade.account_id == account_id, Trade.closed_at.isnot(None))
            .order_by(Trade.closed_at.desc())
            .limit(10)
        )
    )
    consecutive = 0
    for t in last_closed.scalars().all():
        if (t.net_pnl_usdt or 0) >= 0:
            break
        consecutive += 1
    return int(open_count), daily_pnl, consecutive


async def prepare_manual_trade(session: AsyncSession, payload: ManualTradeCreate) -> dict:
    """
    Prepara el diccionario para crear un trade: datos base + entry_notional, margin_used_usdt,
    entry_fee, capital_before_usdt. Valida margen y risk profile si hay account_id.
    Si hay risk_profile_id con sizing_mode, puede sobrescribir quantity.
    """
    data = manual_create_to_trade(payload)
    qty = Decimal(str(payload.quantity))
    entry_price = Decimal(str(payload.entry_price))
    risk_profile_id = getattr(payload, "risk_profile_id", None)
    account_id = getattr(payload, "account_id", None)

    profile = None
    if risk_profile_id:
        r = await session.execute(select(RiskProfile).where(RiskProfile.id == risk_profile_id))
        profile = r.scalar_one_or_none()
        if profile:
            data["risk_profile_id"] = risk_profile_id
            equity = Decimal("0")
            if account_id:
                acc = (await session.execute(select(PaperAccount).where(PaperAccount.id == account_id))).scalar_one_or_none()
                if acc:
                    equity = (acc.current_balance_usdt or 0) + (acc.unrealized_pnl_usdt or 0)
            if profile.sizing_mode == SIZING_FIXED_QTY and profile.fixed_quantity:
                qty = calc_position_size_by_fixed_qty(profile.fixed_quantity)
            elif profile.sizing_mode == SIZING_FIXED_NOTIONAL and profile.fixed_notional_usdt:
                qty = calc_position_size_by_fixed_notional(profile.fixed_notional_usdt, entry_price)
            elif profile.sizing_mode == SIZING_RISK_PCT and profile.risk_pct_per_trade and payload.stop_loss:
                qty = calc_position_size_by_risk_pct(
                    entry_price,
                    Decimal(str(payload.stop_loss)),
                    equity,
                    profile.risk_pct_per_trade,
                    payload.position_side,
                )
            if qty and qty > 0:
                data["quantity"] = qty

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
            if profile:
                equity = (account.current_balance_usdt or 0) + (account.unrealized_pnl_usdt or 0)
                open_count, daily_pnl, consecutive = await _get_risk_context(session, account_id)
                ok_risk, msg_risk = validate_risk_limits(
                    equity,
                    account.available_balance_usdt,
                    account.used_margin_usdt,
                    open_count,
                    daily_pnl,
                    profile,
                    margin_used,
                    payload.leverage,
                    consecutive,
                )
                if not ok_risk:
                    raise ValueError(msg_risk)
    return data


def n8n_create_to_trade(d: N8nTradeCreate, data_override: dict | None = None) -> dict:
    """Convert N8nTradeCreate to Trade ORM kwargs. data_override puede traer quantity/entry_notional/margin_used_usdt/entry_fee/capital_before de prepare_n8n_trade."""
    out = {
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
    if getattr(d, "account_id", None) is not None:
        out["account_id"] = d.account_id
    if getattr(d, "risk_profile_id", None) is not None:
        out["risk_profile_id"] = d.risk_profile_id
    if getattr(d, "idempotency_key", None):
        out["idempotency_key"] = d.idempotency_key
    if data_override:
        out.update(data_override)
    return out


async def prepare_n8n_trade(session: AsyncSession, payload: N8nTradeCreate) -> dict:
    """
    Prepara datos para crear un trade desde n8n: validación de idempotencia, cuenta, risk profile y sizing.
    Lanza ValueError con mensaje apropiado si no se puede abrir (duplicado, capital, riesgo).
    Retorna dict con entry_notional, margin_used_usdt, entry_fee, capital_before_usdt y opcionalmente quantity.
    """
    if getattr(payload, "idempotency_key", None):
        dup = await session.execute(
            select(Trade).where(Trade.idempotency_key == payload.idempotency_key)
        )
        if dup.scalar_one_or_none():
            raise ValueError("DUPLICATE_SIGNAL")

    qty = Decimal(str(payload.quantity))
    entry_price = Decimal(str(payload.entry_price))
    risk_profile_id = getattr(payload, "risk_profile_id", None)
    account_id = getattr(payload, "account_id", None)

    profile = None
    if risk_profile_id:
        r = await session.execute(select(RiskProfile).where(RiskProfile.id == risk_profile_id))
        profile = r.scalar_one_or_none()
        if profile:
            equity = Decimal("0")
            if account_id:
                acc = (await session.execute(select(PaperAccount).where(PaperAccount.id == account_id))).scalar_one_or_none()
                if acc:
                    equity = (acc.current_balance_usdt or 0) + (acc.unrealized_pnl_usdt or 0)
            if profile.sizing_mode == SIZING_FIXED_QTY and profile.fixed_quantity:
                qty = calc_position_size_by_fixed_qty(profile.fixed_quantity)
            elif profile.sizing_mode == SIZING_FIXED_NOTIONAL and profile.fixed_notional_usdt:
                qty = calc_position_size_by_fixed_notional(profile.fixed_notional_usdt, entry_price)
            elif profile.sizing_mode == SIZING_RISK_PCT and profile.risk_pct_per_trade and payload.stop_loss:
                qty = calc_position_size_by_risk_pct(
                    entry_price,
                    Decimal(str(payload.stop_loss)),
                    equity,
                    profile.risk_pct_per_trade,
                    payload.position_side,
                )

    entry_notional = (qty * entry_price).quantize(Decimal("0.0001"))
    margin_used = calc_margin_used(entry_notional, payload.leverage)
    engine = await get_default_fee_engine(session)
    rate = engine.config.taker_rate()
    entry_fee = calc_entry_fee(entry_notional, rate)

    data_override = {
        "entry_notional": entry_notional,
        "margin_used_usdt": margin_used,
        "entry_fee": entry_fee,
        "quantity": qty,
    }

    if account_id is not None:
        result = await session.execute(select(PaperAccount).where(PaperAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError("Cuenta paper no encontrada")
        data_override["capital_before_usdt"] = account.current_balance_usdt
        ok, msg = validate_can_open_trade(
            account.available_balance_usdt,
            margin_used,
            entry_fee,
        )
        if not ok:
            raise ValueError(msg)
        if profile:
            equity = (account.current_balance_usdt or 0) + (account.unrealized_pnl_usdt or 0)
            open_count, daily_pnl, consecutive = await _get_risk_context(session, account_id)
            ok_risk, msg_risk = validate_risk_limits(
                equity,
                account.available_balance_usdt,
                account.used_margin_usdt,
                open_count,
                daily_pnl,
                profile,
                margin_used,
                payload.leverage,
                consecutive,
            )
            if not ok_risk:
                raise ValueError("RISK_LIMIT_BLOCK:" + msg_risk)

    return data_override


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

    await bot_log_event(
        session,
        "INFO",
        MODULE_TRADE,
        EVENT_TRADE_CLOSED,
        f"Trade #{trade_id} closed: {payload.exit_reason}",
        context={"exit_reason": payload.exit_reason, "net_pnl_usdt": str(res.net_pnl_usdt)},
        related_trade_id=trade_id,
    )
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
