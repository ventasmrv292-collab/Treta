"""Stream de precio en tiempo real por WebSocket (Binance WS o poll cada pocos segundos)."""
import asyncio
import json
import logging
from typing import Any

import websockets
from starlette.websockets import WebSocket

from app.config import settings
from app.services.market_data import MarketDataService, _is_render_or_prefer_coingecko

logger = logging.getLogger(__name__)

_connections: set[WebSocket] = set()
_last_price: str | None = None
_POLL_INTERVAL = 2.0  # segundos cuando no hay Binance WS


def register(ws: WebSocket) -> None:
    _connections.add(ws)


def unregister(ws: WebSocket) -> None:
    _connections.discard(ws)


async def broadcast(price: str, symbol: str = "BTCUSDT") -> None:
    global _last_price
    _last_price = price
    msg = json.dumps({"symbol": symbol, "price": price})
    dead: list[WebSocket] = []
    for ws in list(_connections):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.discard(ws)


async def _run_binance_ws() -> None:
    """Conecta al stream de mark price de Binance y reenvía a los clientes."""
    base = getattr(settings, "binance_futures_ws_url", "wss://fstream.binance.com/ws") or "wss://fstream.binance.com/ws"
    url = f"{base.rstrip('/')}/btcusdt@markPrice"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                        if isinstance(data, dict) and "p" in data:
                            await broadcast(data["p"])
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.warning("Binance WS reconectando en 5s: %s", e)
        await asyncio.sleep(5)


async def _run_poll_broadcast() -> None:
    """Cuando Binance no está disponible, consulta precio cada pocos segundos y emite por WS."""
    svc = MarketDataService()
    try:
        price = await svc.get_current_price("BTCUSDT")
        await broadcast(str(price))
    except Exception:
        pass
    while True:
        try:
            price = await svc.get_current_price("BTCUSDT")
            await broadcast(str(price))
        except Exception as e:
            logger.debug("price_stream poll: %s", e)
        await asyncio.sleep(_POLL_INTERVAL)


async def run_price_stream() -> None:
    """Tarea en segundo plano: emite precio en tiempo real a todos los clientes WS."""
    use_coingecko = _is_render_or_prefer_coingecko()
    if use_coingecko:
        logger.info("Precio en tiempo real: modo poll cada %.1fs (CoinGecko)", _POLL_INTERVAL)
        await _run_poll_broadcast()
    else:
        logger.info("Precio en tiempo real: stream Binance mark price")
        await _run_binance_ws()


def get_last_price() -> str | None:
    return _last_price
