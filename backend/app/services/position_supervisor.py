"""
Supervisor de posiciones abiertas: actualiza PnL no realizado por cuenta y cierra por TP/SL.
No usa el frontend; se ejecuta en segundo plano en el backend.
"""
import asyncio
import logging
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.trade import Trade
from app.models.paper_account import PaperAccount
from app.services.trade_service import close_trade_and_compute_pnl
from app.services.trading_capital import calc_gross_pnl
from app.services.market_data import MarketDataService
from app.services.price_stream import get_last_price
from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_SUPERVISOR,
    EVENT_TP_HIT,
    EVENT_SL_HIT,
    EVENT_SUPERVISOR_ERROR,
    EVENT_SUPERVISOR_PNL_UPDATE,
)
from app.schemas.trade import ManualTradeClose

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 15.0
SYMBOL_PRICE = "BTCUSDT"

# Estado del supervisor (para API de estado)
_last_cycle_at: float | None = None


def get_supervisor_status() -> dict:
    """Estado del supervisor para la UI."""
    import time
    return {
        "running": True,
        "last_cycle_at": _last_cycle_at,
        "check_interval_seconds": CHECK_INTERVAL,
    }


async def _get_current_price() -> Decimal | None:
    last = get_last_price()
    if last is not None:
        try:
            return Decimal(last)
        except Exception:
            pass
    try:
        svc = MarketDataService()
        p = await svc.get_current_price(SYMBOL_PRICE)
        return p
    except Exception as e:
        logger.debug("supervisor: no se pudo obtener precio: %s", e)
        return None


async def _update_unrealized_pnl(session: AsyncSession, price: Decimal) -> None:
    """Actualiza unrealized_pnl_usdt por cuenta según posiciones abiertas BTCUSDT."""
    result = await session.execute(
        select(Trade).where(
            Trade.closed_at.is_(None),
            Trade.symbol == SYMBOL_PRICE,
            Trade.account_id.isnot(None),
        )
    )
    trades = list(result.scalars().all())
    by_account: dict[int, Decimal] = defaultdict(Decimal)
    for t in trades:
        gross = calc_gross_pnl(
            t.position_side,
            t.entry_price,
            price,
            t.quantity,
        )
        by_account[t.account_id] += gross
    for acc_id, unrealized in by_account.items():
        r = await session.execute(select(PaperAccount).where(PaperAccount.id == acc_id))
        acc = r.scalar_one_or_none()
        if acc:
            acc.unrealized_pnl_usdt = unrealized.quantize(Decimal("0.0001"))
            acc.available_balance_usdt = acc.current_balance_usdt + acc.unrealized_pnl_usdt - acc.used_margin_usdt
    if by_account:
        await bot_log_event(
            session,
            "DEBUG",
            MODULE_SUPERVISOR,
            EVENT_SUPERVISOR_PNL_UPDATE,
            f"Unrealized PnL actualizado para {len(by_account)} cuentas",
            context={str(k): str(v) for k, v in by_account.items()},
        )


async def _check_and_close_trades(session: AsyncSession, price: Decimal) -> None:
    """Cierra operaciones que toquen TP o SL y registra TP_HIT/SL_HIT."""
    result = await session.execute(
        select(Trade).where(
            Trade.closed_at.is_(None),
            (Trade.take_profit.isnot(None)) | (Trade.stop_loss.isnot(None)),
            Trade.symbol == SYMBOL_PRICE,
        )
    )
    trades = list(result.scalars().all())
    for trade in trades:
        try:
            payload: ManualTradeClose | None = None
            event_type: str | None = None
            if trade.position_side == "LONG":
                if trade.take_profit is not None and price >= trade.take_profit:
                    payload = ManualTradeClose(
                        exit_price=trade.take_profit,
                        exit_order_type="LIMIT",
                        maker_taker_exit="MAKER",
                        exit_reason="take_profit",
                    )
                    event_type = EVENT_TP_HIT
                elif trade.stop_loss is not None and price <= trade.stop_loss:
                    payload = ManualTradeClose(
                        exit_price=trade.stop_loss,
                        exit_order_type="MARKET",
                        maker_taker_exit="TAKER",
                        exit_reason="stop_loss",
                    )
                    event_type = EVENT_SL_HIT
            else:
                if trade.take_profit is not None and price <= trade.take_profit:
                    payload = ManualTradeClose(
                        exit_price=trade.take_profit,
                        exit_order_type="LIMIT",
                        maker_taker_exit="MAKER",
                        exit_reason="take_profit",
                    )
                    event_type = EVENT_TP_HIT
                elif trade.stop_loss is not None and price >= trade.stop_loss:
                    payload = ManualTradeClose(
                        exit_price=trade.stop_loss,
                        exit_order_type="MARKET",
                        maker_taker_exit="TAKER",
                        exit_reason="stop_loss",
                    )
                    event_type = EVENT_SL_HIT
            if payload is not None and event_type:
                closed = await close_trade_and_compute_pnl(session, trade.id, payload)
                if closed:
                    await bot_log_event(
                        session,
                        "INFO",
                        MODULE_SUPERVISOR,
                        event_type,
                        f"Trade #{trade.id} cerrado por {payload.exit_reason} a {payload.exit_price}",
                        context={"trade_id": trade.id, "exit_reason": payload.exit_reason},
                        related_trade_id=trade.id,
                    )
        except Exception as e:
            logger.warning("supervisor: error cerrando trade #%s: %s", trade.id, e)
            await bot_log_event(
                session,
                "ERROR",
                MODULE_SUPERVISOR,
                EVENT_SUPERVISOR_ERROR,
                f"Error cerrando trade #{trade.id}: {e}",
                context={"trade_id": trade.id, "error": str(e)},
                related_trade_id=trade.id,
            )
            raise


async def run_supervisor_cycle() -> None:
    """Un ciclo: precio, actualizar unrealized, revisar TP/SL."""
    global _last_cycle_at
    import time
    _last_cycle_at = time.time()
    price = await _get_current_price()
    if price is None:
        return
    async with async_session_maker() as session:
        try:
            await _update_unrealized_pnl(session, price)
            await session.commit()
        except Exception as e:
            logger.warning("supervisor: error actualizando PnL: %s", e)
            await session.rollback()
            async with async_session_maker() as log_session:
                await bot_log_event(
                    log_session,
                    "ERROR",
                    MODULE_SUPERVISOR,
                    EVENT_SUPERVISOR_ERROR,
                    f"Error actualizando unrealized PnL: {e}",
                    context={"error": str(e)},
                )
                await log_session.commit()
            return
    async with async_session_maker() as session:
        try:
            await _check_and_close_trades(session, price)
            await session.commit()
        except Exception as e:
            logger.warning("supervisor: %s", e)
            await session.rollback()


async def run_position_supervisor() -> None:
    """Bucle principal del supervisor."""
    logger.info("Position supervisor iniciado (cada %.0fs)", CHECK_INTERVAL)
    while True:
        try:
            await run_supervisor_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("position_supervisor: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
