"""Seed database with strategies, fee configs and sample trades."""
import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker, engine
from app.db.base import Base
from app.models.strategy import Strategy
from app.models.fee_config import FeeConfig
from app.models.trade import Trade


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_strategies(session: AsyncSession):
    strategies = [
        Strategy(
            family="BREAKOUT",
            name="breakout_volume_v1",
            version="1.0",
            description="Breakout basado en volumen",
            default_params_json='{"volume_mult": 2.0, "atr_period": 14}',
            active=True,
        ),
        Strategy(
            family="MEAN_REVERSION",
            name="vwap_snapback_v1",
            version="1.0",
            description="Mean reversion a VWAP",
            default_params_json='{"vwap_deviation": 0.002}',
            active=True,
        ),
        Strategy(
            family="TREND_PULLBACK",
            name="ema_pullback_v1",
            version="1.0",
            description="Pullback a EMA en tendencia",
            default_params_json='{"ema_fast": 9, "ema_slow": 21}',
            active=True,
        ),
    ]
    for s in strategies:
        session.add(s)
    await session.flush()
    await session.commit()
    print("Strategies seeded.")


async def seed_fee_configs(session: AsyncSession):
    configs = [
        FeeConfig(
            name="conservative",
            maker_fee_bps=Decimal("3"),
            taker_fee_bps=Decimal("5"),
            bnb_discount_pct=Decimal("0"),
            default_slippage_bps=Decimal("5"),
            include_funding=True,
            is_default=False,
        ),
        FeeConfig(
            name="realistic",
            maker_fee_bps=Decimal("2"),
            taker_fee_bps=Decimal("4"),
            bnb_discount_pct=Decimal("10"),
            default_slippage_bps=Decimal("2"),
            include_funding=True,
            is_default=True,
        ),
        FeeConfig(
            name="optimistic",
            maker_fee_bps=Decimal("1.5"),
            taker_fee_bps=Decimal("3"),
            bnb_discount_pct=Decimal("25"),
            default_slippage_bps=Decimal("0"),
            include_funding=True,
            is_default=False,
        ),
    ]
    for c in configs:
        session.add(c)
    await session.commit()
    print("Fee configs seeded.")


async def seed_trades(session: AsyncSession):
    now = datetime.now(timezone.utc)
    base = now - timedelta(days=14)
    trades_data = [
        {
            "source": "manual",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": "BREAKOUT",
            "strategy_name": "breakout_volume_v1",
            "strategy_version": "1.0",
            "timeframe": "15m",
            "position_side": "LONG",
            "order_side_entry": "BUY",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 10,
            "quantity": Decimal("0.001"),
            "entry_price": Decimal("67500"),
            "take_profit": Decimal("68200"),
            "stop_loss": Decimal("67200"),
            "exit_price": Decimal("68100"),
            "exit_order_type": "MARKET",
            "maker_taker_exit": "TAKER",
            "exit_reason": "take_profit",
            "closed_at": base + timedelta(hours=2),
            "entry_notional": Decimal("67.5"),
            "exit_notional": Decimal("68.1"),
            "entry_fee": Decimal("0.027"),
            "exit_fee": Decimal("0.02724"),
            "funding_fee": Decimal("0"),
            "slippage_usdt": Decimal("0"),
            "gross_pnl_usdt": Decimal("0.6"),
            "net_pnl_usdt": Decimal("0.54576"),
            "pnl_pct_notional": Decimal("0.81"),
            "pnl_pct_margin": Decimal("8.1"),
        },
        {
            "source": "n8n",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": "MEAN_REVERSION",
            "strategy_name": "vwap_snapback_v1",
            "strategy_version": "1.0",
            "timeframe": "1h",
            "position_side": "SHORT",
            "order_side_entry": "SELL",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 20,
            "quantity": Decimal("0.002"),
            "entry_price": Decimal("67800"),
            "take_profit": Decimal("67200"),
            "stop_loss": Decimal("68100"),
            "exit_price": Decimal("67300"),
            "exit_order_type": "LIMIT",
            "maker_taker_exit": "MAKER",
            "exit_reason": "take_profit",
            "closed_at": base + timedelta(days=1, hours=3),
            "entry_notional": Decimal("135.6"),
            "exit_notional": Decimal("134.6"),
            "entry_fee": Decimal("0.05424"),
            "exit_fee": Decimal("0.02692"),
            "funding_fee": Decimal("0"),
            "slippage_usdt": Decimal("0"),
            "gross_pnl_usdt": Decimal("1.0"),
            "net_pnl_usdt": Decimal("0.91884"),
            "pnl_pct_notional": Decimal("0.74"),
            "pnl_pct_margin": Decimal("14.7"),
        },
        {
            "source": "manual",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": "TREND_PULLBACK",
            "strategy_name": "ema_pullback_v1",
            "strategy_version": "1.0",
            "timeframe": "5m",
            "position_side": "LONG",
            "order_side_entry": "BUY",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 10,
            "quantity": Decimal("0.0015"),
            "entry_price": Decimal("67000"),
            "take_profit": Decimal("67800"),
            "stop_loss": Decimal("66700"),
            "exit_price": Decimal("66600"),
            "exit_order_type": "MARKET",
            "maker_taker_exit": "TAKER",
            "exit_reason": "stop_loss",
            "closed_at": base + timedelta(days=2),
            "entry_notional": Decimal("100.5"),
            "exit_notional": Decimal("99.9"),
            "entry_fee": Decimal("0.0402"),
            "exit_fee": Decimal("0.03996"),
            "funding_fee": Decimal("0"),
            "slippage_usdt": Decimal("0"),
            "gross_pnl_usdt": Decimal("-0.6"),
            "net_pnl_usdt": Decimal("-0.68016"),
            "pnl_pct_notional": Decimal("-0.6"),
            "pnl_pct_margin": Decimal("-6"),
        },
        {
            "source": "manual",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": "BREAKOUT",
            "strategy_name": "breakout_volume_v1",
            "strategy_version": "1.0",
            "timeframe": "15m",
            "position_side": "LONG",
            "order_side_entry": "BUY",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 10,
            "quantity": Decimal("0.001"),
            "entry_price": Decimal("68000"),
            "take_profit": Decimal("68800"),
            "stop_loss": Decimal("67700"),
            "exit_price": None,
            "exit_order_type": None,
            "maker_taker_exit": None,
            "exit_reason": None,
            "closed_at": None,
            "entry_notional": None,
            "exit_notional": None,
            "entry_fee": None,
            "exit_fee": None,
            "funding_fee": None,
            "slippage_usdt": None,
            "gross_pnl_usdt": None,
            "net_pnl_usdt": None,
            "pnl_pct_notional": None,
            "pnl_pct_margin": None,
        },
    ]
    for t in trades_data:
        session.add(Trade(**t))
    await session.commit()
    print("Sample trades seeded.")


async def main():
    await create_tables()
    async with async_session_maker() as session:
        result = await session.execute(select(Strategy).limit(1))
        if result.scalar_one_or_none() is None:
            await seed_strategies(session)
        result = await session.execute(select(FeeConfig).limit(1))
        if result.scalar_one_or_none() is None:
            await seed_fee_configs(session)
        result = await session.execute(select(Trade).limit(1))
        if result.scalar_one_or_none() is None:
            await seed_trades(session)
    print("Seed completed.")


if __name__ == "__main__":
    asyncio.run(main())
