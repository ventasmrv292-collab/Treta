"""Tipos comunes para señales de estrategias."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class StrategySignal:
    """Señal generada por una estrategia (entrada)."""
    strategy_family: str
    strategy_name: str
    strategy_version: str
    symbol: str
    timeframe: str
    position_side: str  # LONG | SHORT
    entry_price: Decimal
    take_profit: Decimal | None
    stop_loss: Decimal | None
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None  # payload_json

    def to_trade_payload(self, quantity: Decimal, leverage: int = 10) -> dict[str, Any]:
        return {
            "strategy_family": self.strategy_family,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "position_side": self.position_side,
            "entry_price": self.entry_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "quantity": quantity,
            "leverage": leverage,
            "metadata": self.metadata or {},
        }
