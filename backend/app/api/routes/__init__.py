"""API routes."""
from fastapi import APIRouter
from app.api.routes import trades, strategies, fee_config, candles, market, webhook, analytics, backtest, ws

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(fee_config.router, prefix="/fee-config", tags=["fee-config"])
api_router.include_router(candles.router, prefix="/candles", tags=["candles"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
