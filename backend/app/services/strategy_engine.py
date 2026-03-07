"""
Motor de estrategias: carga estrategias activas, obtiene velas de DB, ejecuta estrategias,
genera señales y las ejecuta (signal_event -> validación riesgo -> trade -> ledger -> logs).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.strategy import Strategy
from app.models.candle import Candle
from app.models.trade import Trade
from app.models.paper_account import PaperAccount
from app.models.risk_profile import RiskProfile
from app.models.signal_event import SignalEvent
from app.models.account_ledger import AccountLedger
from app.services.strategies import get_strategy_fn, STRATEGY_REGISTRY
from app.services.strategies.base import StrategySignal
from app.services.trade_service import prepare_n8n_trade, n8n_create_to_trade
from app.schemas.trade import N8nTradeCreate
from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_STRATEGY,
    EVENT_STRATEGY_SIGNAL_CREATED,
    EVENT_SIGNAL_REJECTED,
    EVENT_TRADE_OPENED,
    EVENT_RISK_LIMIT_BLOCK,
    EVENT_DUPLICATE_SIGNAL,
)
from app.services.trading_capital import calc_margin_used

logger = logging.getLogger(__name__)

SYMBOL = "BTCUSDT"
CANDLES_LIMIT = 200
DEFAULT_LEVERAGE = 10
DEFAULT_QUANTITY = Decimal("0.001")


async def _get_default_account_and_profile(session: AsyncSession) -> tuple[int | None, int | None]:
    """Primera cuenta paper activa y primer risk profile (si existen)."""
    r = await session.execute(select(PaperAccount).where(PaperAccount.status == "ACTIVE").order_by(PaperAccount.id).limit(1))
    acc = r.scalar_one_or_none()
    from app.models.risk_profile import RiskProfile
    rp = await session.execute(select(RiskProfile).order_by(RiskProfile.id).limit(1))
    profile = rp.scalar_one_or_none()
    return (acc.id if acc else None, profile.id if profile else None)


def _signal_to_n8n_payload(
    signal: StrategySignal,
    account_id: int | None,
    risk_profile_id: int | None,
    idempotency_key: str,
    quantity: Decimal,
    leverage: int,
) -> N8nTradeCreate:
    return N8nTradeCreate(
        source="BACKEND",
        symbol=signal.symbol,
        market="PERP",
        strategy_family=signal.strategy_family,
        strategy_name=signal.strategy_name,
        strategy_version=signal.strategy_version,
        timeframe=signal.timeframe,
        position_side=signal.position_side,
        leverage=leverage,
        entry_price=signal.entry_price,
        take_profit=signal.take_profit,
        stop_loss=signal.stop_loss,
        quantity=quantity,
        entry_order_type="MARKET",
        maker_taker_entry="TAKER",
        signal_timestamp=datetime.now(timezone.utc),
        strategy_params_json=json.dumps(signal.metadata, default=str) if signal.metadata else None,
        notes=f"Auto signal {signal.strategy_name}",
        account_id=account_id,
        risk_profile_id=risk_profile_id,
        idempotency_key=idempotency_key,
    )


async def _execute_signal(
    session: AsyncSession,
    signal: StrategySignal,
    account_id: int | None,
    risk_profile_id: int | None,
    strategy_id: int | None = None,
) -> Trade | None:
    """Crea signal_event, valida riesgo y capital, crea trade y ledger. Retorna trade si se abrió, None si rechazado."""
    idempotency_key = f"backend|{signal.strategy_family}|{signal.strategy_name}|{signal.timeframe}|{signal.entry_price}|{signal.symbol}"
    payload = _signal_to_n8n_payload(signal, account_id, risk_profile_id, idempotency_key, DEFAULT_QUANTITY, DEFAULT_LEVERAGE)
    payload_json = json.dumps({
        "position_side": signal.position_side,
        "entry_price": str(signal.entry_price),
        "take_profit": str(signal.take_profit) if signal.take_profit else None,
        "stop_loss": str(signal.stop_loss) if signal.stop_loss else None,
        "metadata": signal.metadata,
    }, default=str)
    signal_event = SignalEvent(
        source="BACKEND",
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_family=signal.strategy_family,
        strategy_name=signal.strategy_name,
        strategy_version=signal.strategy_version,
        payload_json=payload_json,
        status="RECEIVED",
        idempotency_key=idempotency_key,
    )
    session.add(signal_event)
    await session.flush()

    try:
        data_override = await prepare_n8n_trade(session, payload)
    except ValueError as e:
        msg = str(e)
        if "DUPLICATE" in msg:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = "DUPLICATE_SIGNAL"
            await bot_log_event(session, "WARN", MODULE_STRATEGY, EVENT_DUPLICATE_SIGNAL, f"Signal rejected: {msg}", context={"idempotency_key": idempotency_key}, related_signal_event_id=signal_event.id)
        elif "RISK_LIMIT" in msg:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = msg
            await bot_log_event(session, "WARN", MODULE_STRATEGY, EVENT_RISK_LIMIT_BLOCK, f"Signal rejected: {msg}", context={"reason": msg}, related_signal_event_id=signal_event.id)
        else:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = msg
            await bot_log_event(session, "WARN", MODULE_STRATEGY, EVENT_SIGNAL_REJECTED, f"Signal rejected: {msg}", context={"reason": msg}, related_signal_event_id=signal_event.id)
        await session.commit()
        return None

    data = n8n_create_to_trade(payload, data_override)
    trade = Trade(**data)
    trade.signal_event_id = signal_event.id
    if strategy_id is not None:
        trade.strategy_id = strategy_id
    session.add(trade)
    await session.flush()

    signal_event.status = "ACCEPTED"
    signal_event.trade_id = trade.id
    signal_event.processed_at = datetime.now(timezone.utc)

    # Ledger: TRADE_OPEN
    if trade.account_id is not None:
        acc = (await session.execute(select(PaperAccount).where(PaperAccount.id == trade.account_id))).scalar_one_or_none()
        if acc:
            balance_before = acc.current_balance_usdt or Decimal("0")
            acc.used_margin_usdt = (acc.used_margin_usdt or Decimal("0")) + (trade.margin_used_usdt or Decimal("0"))
            acc.current_balance_usdt = balance_before - (trade.entry_fee or Decimal("0"))
            acc.available_balance_usdt = acc.current_balance_usdt - acc.used_margin_usdt
            balance_after = acc.current_balance_usdt
            ledger = AccountLedger(
                account_id=trade.account_id,
                trade_id=trade.id,
                event_type="TRADE_OPEN",
                amount_usdt=-(trade.entry_fee or Decimal("0")) - (trade.margin_used_usdt or Decimal("0")),
                balance_before_usdt=balance_before,
                balance_after_usdt=balance_after,
                meta_json=json.dumps({"trade_id": trade.id, "entry_fee": str(trade.entry_fee), "margin_used": str(trade.margin_used_usdt)}),
            )
            session.add(ledger)

    await bot_log_event(
        session,
        "INFO",
        MODULE_STRATEGY,
        EVENT_STRATEGY_SIGNAL_CREATED,
        f"Trade #{trade.id} opened from signal: {signal.strategy_name} {signal.position_side}",
        context={"trade_id": trade.id, "strategy": signal.strategy_name, "position_side": signal.position_side},
        related_trade_id=trade.id,
        related_signal_event_id=signal_event.id,
    )
    await bot_log_event(
        session,
        "INFO",
        "trade_service",
        EVENT_TRADE_OPENED,
        f"Trade #{trade.id} opened: {trade.symbol} {trade.position_side}",
        context={"symbol": trade.symbol, "position_side": trade.position_side},
        related_trade_id=trade.id,
    )
    await session.commit()
    return trade


async def run_strategies_for_timeframe(interval: str) -> list[Trade]:
    """
    Carga estrategias activas que apliquen al intervalo, obtiene velas cerradas de DB,
    ejecuta cada estrategia y procesa señales. Retorna lista de trades abiertos en esta ejecución.
    """
    opened: list[Trade] = []
    async with async_session_maker() as session:
        result = await session.execute(
            select(Strategy).where(Strategy.active == True).order_by(Strategy.id)
        )
        strategies = list(result.scalars().all())
        if not strategies:
            return opened

        candles_result = await session.execute(
            select(Candle)
            .where(Candle.symbol == SYMBOL, Candle.interval == interval, Candle.is_closed == True)
            .order_by(Candle.open_time.desc())
            .limit(CANDLES_LIMIT)
        )
        rows = list(candles_result.scalars().all())
        candles = [
            {
                "symbol": c.symbol,
                "open_time": c.open_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in reversed(rows)
        ]
        if len(candles) < 20:
            logger.debug("strategy_engine: not enough candles for %s (%d)", interval, len(candles))
            return opened

        account_id, risk_profile_id = await _get_default_account_and_profile(session)

        for strat in strategies:
            fn = get_strategy_fn(strat.family, strat.name, strat.version)
            if not fn:
                continue
            try:
                params = {}
                if strat.default_params_json:
                    try:
                        params = json.loads(strat.default_params_json)
                    except Exception:
                        pass
                params["timeframe"] = interval
                signal = fn(candles, params)
                if signal is None:
                    continue
                # Ejecutar en una nueva sesión para cada señal (commit aislado)
                async with async_session_maker() as exec_session:
                    trade = await _execute_signal(exec_session, signal, account_id, risk_profile_id, strategy_id=strat.id)
                    if trade:
                        opened.append(trade)
            except Exception as e:
                logger.exception("strategy_engine: %s/%s failed: %s", strat.family, strat.name, e)
    return opened
