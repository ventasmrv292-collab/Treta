"""
Servicio de datos de mercado: reexporta MarketDataService desde market_data.
Usado por candle_sync, strategy_engine (precio) y rutas de market/candles.
"""
from app.services.market_data import MarketDataService

__all__ = ["MarketDataService"]
