"""WebSocket: precio en tiempo real."""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.price_stream import get_last_price, register, unregister

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/price")
async def ws_price(websocket: WebSocket):
    await websocket.accept()
    register(websocket)
    try:
        last = get_last_price()
        if last is not None:
            await websocket.send_text(json.dumps({"symbol": "BTCUSDT", "price": last}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unregister(websocket)
