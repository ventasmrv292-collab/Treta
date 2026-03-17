"""
Cierre automático de operaciones cuando el precio alcanza Take Profit o Stop Loss.
Se ejecuta en segundo plano cada CHECK_INTERVAL segundos.
"""
import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select, or_

from app.db.session import async_session_maker
from app.models.trade import Trade
from app.services.trade_service import close_trade_and_compute_pnl
from app.services.market_data import MarketDataService
from app.services.price_stream import get_last_price
from app.schemas.trade import ManualTradeClose

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 15.0  # segundos
SYMBOL_PRICE = "BTCUSDT"  # por ahora solo BTCUSDT


async def _get_current_price() -> Decimal | None:
    """Obtiene precio actual: primero del stream, si no del API."""
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
        logger.debug("tp_sl_checker: no se pudo obtener precio: %s", e)
        return None


async def _check_and_close_trades() -> None:
    """Obtiene operaciones abiertas con TP/SL, precio actual, y cierra las que toquen nivel."""
    price = await _get_current_price()
    if price is None:
        return
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(Trade).where(
                    Trade.closed_at.is_(None),
                    or_(Trade.take_profit.isnot(None), Trade.stop_loss.isnot(None)),
                    Trade.symbol == SYMBOL_PRICE,
                )
            )
            trades = list(result.scalars().all())
        except Exception as e:
            logger.warning("tp_sl_checker: error cargando trades: %s", e)
            return
        for trade in trades:
            try:
                payload: ManualTradeClose | None = None
                if trade.position_side == "LONG":
                    if trade.take_profit is not None and price >= trade.take_profit:
                        payload = ManualTradeClose(
                            exit_price=trade.take_profit,
                            exit_order_type="LIMIT",
                            maker_taker_exit="MAKER",
                            exit_reason="take_profit",
                        )
                    elif trade.stop_loss is not None and price <= trade.stop_loss:
                        payload = ManualTradeClose(
                            exit_price=trade.stop_loss,
                            exit_order_type="MARKET",
                            maker_taker_exit="TAKER",
                            exit_reason="stop_loss",
                        )
                else:
                    if trade.take_profit is not None and price <= trade.take_profit:
                        payload = ManualTradeClose(
                            exit_price=trade.take_profit,
                            exit_order_type="LIMIT",
                            maker_taker_exit="MAKER",
                            exit_reason="take_profit",
                        )
                    elif trade.stop_loss is not None and price >= trade.stop_loss:
                        payload = ManualTradeClose(
                            exit_price=trade.stop_loss,
                            exit_order_type="MARKET",
                            maker_taker_exit="TAKER",
                            exit_reason="stop_loss",
                        )
                if payload is not None:
                    closed = await close_trade_and_compute_pnl(session, trade.id, payload)
                    if closed:
                        await session.commit()
                        logger.info(
                            "tp_sl_checker: operación #%s cerrada por %s a %s",
                            trade.id,
                            payload.exit_reason,
                            payload.exit_price,
                        )
            except Exception as e:
                logger.warning("tp_sl_checker: error cerrando trade #%s: %s", trade.id, e)
                await session.rollback()


async def run_tp_sl_checker() -> None:
    """Bucle que revisa TP/SL cada CHECK_INTERVAL segundos."""
    logger.info("TP/SL checker iniciado (cada %.0fs)", CHECK_INTERVAL)
    while True:
        try:
            await _check_and_close_trades()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("tp_sl_checker: %s", e)
        await asyncio.sleep(CHECK_INTERVAL)
