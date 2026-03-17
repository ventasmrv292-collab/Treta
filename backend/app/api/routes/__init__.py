"""API routes."""
from fastapi import APIRouter
from app.api.routes import trades, strategies, fee_config, candles, market, webhook, analytics, backtest, ws, paper_accounts, risk_profiles, bot_logs, supervisor

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(ws.router, prefix="/ws", tags=["ws"])
api_router.include_router(paper_accounts.router, prefix="/paper-accounts", tags=["paper-accounts"])
api_router.include_router(risk_profiles.router, prefix="/risk-profiles", tags=["risk-profiles"])
api_router.include_router(bot_logs.router, prefix="/bot-logs", tags=["bot-logs"])
api_router.include_router(supervisor.router, prefix="/supervisor", tags=["supervisor"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(fee_config.router, prefix="/fee-config", tags=["fee-config"])
api_router.include_router(candles.router, prefix="/candles", tags=["candles"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
