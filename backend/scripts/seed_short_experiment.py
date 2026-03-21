"""
Idempotente: estrategias v2, perfil SHORT_EXPERIMENT_20X_R075, 6 filas runtime SHORT (30m/1h).
Ejecutar desde backend: python -m scripts.seed_short_experiment
"""
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.risk_profile import RiskProfile
from app.models.strategy import Strategy
from app.models.strategy_runtime_config import StrategyRuntimeConfig

SYMBOL = "BTCUSDT"

STRATEGIES_V2 = [
    ("BREAKOUT", "breakout_volume_v2", "2.0.0", "Breakout volumen v2 (LONG/SHORT)"),
    ("MEAN_REVERSION", "vwap_snapback_v2", "2.0.0", "VWAP snapback v2"),
    ("TREND_PULLBACK", "ema_pullback_v2", "2.0.0", "EMA pullback v2"),
]

# cooldown mayor para vwap SHORT (experimental)
SHORT_ROWS = [
    ("breakout_volume_v2", "30m", 0),
    ("breakout_volume_v2", "1h", 0),
    ("vwap_snapback_v2", "30m", 120),
    ("vwap_snapback_v2", "1h", 120),
    ("ema_pullback_v2", "30m", 0),
    ("ema_pullback_v2", "1h", 0),
]


async def main() -> None:
    async with async_session_maker() as session:
        for family, name, version, desc in STRATEGIES_V2:
            r = await session.execute(
                select(Strategy).where(Strategy.family == family, Strategy.name == name, Strategy.version == version)
            )
            if r.scalar_one_or_none() is None:
                session.add(
                    Strategy(
                        family=family,
                        name=name,
                        version=version,
                        description=desc,
                        default_params_json=None,
                        active=True,
                    )
                )
        await session.commit()

        r = await session.execute(select(RiskProfile).where(RiskProfile.name == "SHORT_EXPERIMENT_20X_R075"))
        if r.scalar_one_or_none() is None:
            session.add(
                RiskProfile(
                    name="SHORT_EXPERIMENT_20X_R075",
                    sizing_mode="RISK_PCT_OF_EQUITY",
                    risk_pct_per_trade=Decimal("0.75"),
                    max_open_positions=1,
                    max_margin_pct_of_account=Decimal("100"),
                    allowed_leverage_json=json.dumps([20]),
                )
            )
            await session.commit()

        id_by_name: dict[str, int] = {}
        for family, name, version, _ in STRATEGIES_V2:
            r2 = await session.execute(
                select(Strategy).where(Strategy.family == family, Strategy.name == name, Strategy.version == version)
            )
            s = r2.scalar_one()
            id_by_name[name] = s.id

        for strat_name, tf, cooldown in SHORT_ROWS:
            sid = id_by_name[strat_name]
            r3 = await session.execute(
                select(StrategyRuntimeConfig).where(
                    StrategyRuntimeConfig.strategy_id == sid,
                    StrategyRuntimeConfig.symbol == SYMBOL,
                    StrategyRuntimeConfig.timeframe == tf,
                )
            )
            row = r3.scalar_one_or_none()
            if row is None:
                session.add(
                    StrategyRuntimeConfig(
                        strategy_id=sid,
                        symbol=SYMBOL,
                        timeframe=tf,
                        active=True,
                        allow_long=False,
                        allow_short=True,
                        max_open_positions=1,
                        cooldown_minutes=cooldown,
                    )
                )
            else:
                row.active = True
                row.allow_long = False
                row.allow_short = True
                row.max_open_positions = 1
                row.cooldown_minutes = cooldown
        await session.commit()
        print("seed_short_experiment: OK")


if __name__ == "__main__":
    asyncio.run(main())
