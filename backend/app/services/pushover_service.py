"""
Notificaciones Pushover al abrir y cerrar operaciones.
Requiere PUSHOVER_USER_KEY y PUSHOVER_APP_TOKEN en el entorno.
Si no están definidos, no se envía nada.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx

from app.config import settings

if TYPE_CHECKING:
    from app.models.trade import Trade

logger = logging.getLogger(__name__)

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def _is_configured() -> bool:
    return bool(
        getattr(settings, "pushover_user_key", "").strip()
        and getattr(settings, "pushover_app_token", "").strip()
    )


def _format_price(v: Decimal | None) -> str:
    if v is None:
        return "—"
    return f"{float(v):,.2f}"


async def send_trade_opened(trade: "Trade") -> None:
    """
    Envía notificación Pushover: nueva operación abierta.
    Símbolo, Long/Short, estrategia, entrada, TP, SL.
    No lanza excepción; fallos se registran en log.
    """
    if not _is_configured():
        return
    side = trade.position_side or "—"
    strategy = trade.strategy_name or trade.strategy_family or "—"
    title = f"Nueva operación · {trade.symbol}"
    msg = (
        f"{side}\n"
        f"Estrategia: {strategy}\n"
        f"Entrada: {_format_price(trade.entry_price)}\n"
        f"TP: {_format_price(trade.take_profit)} · SL: {_format_price(trade.stop_loss)}"
    )
    await _send(title=title, message=msg)


async def send_trade_closed(trade: "Trade") -> None:
    """
    Envía notificación Pushover: operación cerrada.
    Long/Short, motivo (TP/SL), ganancia/pérdida, estrategia.
    """
    if not _is_configured():
        return
    side = trade.position_side or "—"
    reason = (trade.exit_reason or "—").replace("_", " ").title()
    strategy = trade.strategy_name or trade.strategy_family or "—"
    net = trade.net_pnl_usdt
    if net is not None:
        pnl_str = f"+{float(net):,.2f} USDT" if net >= 0 else f"{float(net):,.2f} USDT"
    else:
        pnl_str = "—"
    title = f"Operación cerrada · {trade.symbol}"
    msg = (
        f"{side} cerrada · {reason}\n"
        f"PnL: {pnl_str}\n"
        f"Estrategia: {strategy}"
    )
    await _send(title=title, message=msg)


async def _send(title: str, message: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                PUSHOVER_URL,
                data={
                    "user": settings.pushover_user_key.strip(),
                    "token": settings.pushover_app_token.strip(),
                    "title": title,
                    "message": message,
                },
            )
            if r.status_code != 200:
                logger.warning("Pushover: %s %s", r.status_code, r.text)
    except Exception as e:
        logger.warning("Pushover send failed: %s", e)


