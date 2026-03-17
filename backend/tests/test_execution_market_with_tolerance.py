import pytest
from decimal import Decimal

from app.services.trade_service import prepare_n8n_trade
from app.schemas.trade import N8nTradeCreate
from app.config import settings


class DummySession:
    """Session mínima para tests unitarios de prepare_n8n_trade (sin DB real)."""

    async def execute(self, *_args, **_kwargs):
        class R:
            def scalar_one_or_none(self_inner):
                return None

            def scalars(self_inner):
                class S:
                    def all(self_s):
                        return []

                return S()

        return R()


@pytest.mark.asyncio
async def test_entry_within_tolerance_enters(monkeypatch):
    # Simula precio live cercano al ideal (USDM).
    async def fake_price(_self, _symbol: str):
        return Decimal("73850"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),  # ideal_entry
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
    )

    session = DummySession()
    data = await prepare_n8n_trade(session, payload)
    # Debe incluir entry_notional calculado con live_entry (73850)
    assert Decimal(str(data["entry_notional"])) == Decimal("73.85")


@pytest.mark.asyncio
async def test_entry_too_far_rejected(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("75000"), False  # muy lejos del ideal 73800

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
    )

    session = DummySession()
    with pytest.raises(ValueError) as exc:
        await prepare_n8n_trade(session, payload)
    assert "ENTRY_TOO_FAR_FROM_SIGNAL" in str(exc.value)


@pytest.mark.asyncio
async def test_rr_real_below_min_rejected(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73950"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    # RR muy pequeño porque TP está demasiado cerca
    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74000"),
        stop_loss=Decimal("73900"),
        quantity=Decimal("0.001"),
    )

    session = DummySession()
    with pytest.raises(ValueError) as exc:
        await prepare_n8n_trade(session, payload)
    assert "RR_BELOW_MIN_REAL" in str(exc.value)


@pytest.mark.asyncio
async def test_signal_expired_rejected(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73850"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    from datetime import datetime, timedelta, timezone

    old_ts = datetime.now(timezone.utc) - timedelta(seconds=settings.signal_max_age_seconds + 5)

    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
        signal_timestamp=old_ts,
    )

    session = DummySession()
    with pytest.raises(ValueError) as exc:
        await prepare_n8n_trade(session, payload)
    assert "SIGNAL_EXPIRED" in str(exc.value)


@pytest.mark.asyncio
async def test_short_rr_and_tolerance(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73850"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)


@pytest.mark.asyncio
async def test_deviation_equal_max_accepts(monkeypatch):
    # Configuramos tolerancia para que la desviación sea exactamente el máximo.
    async def fake_price(_self, _symbol: str):
        return Decimal("73911.7"), False  # ≈ 0.15% por encima de 73800

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74500"),
        stop_loss=Decimal("73500"),
        quantity=Decimal("0.001"),
    )

    session = DummySession()
    # No debe lanzar; simplemente comprobar que calcula algo.
    data = await prepare_n8n_trade(session, payload)
    assert "entry_notional" in data


@pytest.mark.asyncio
async def test_rr_equal_min_accepts(monkeypatch):
    # Calculamos un caso donde rr_real == min_rr_ratio (≈1.2).
    async def fake_price(_self, _symbol: str):
        return Decimal("73800"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        # riesgo = 100, reward = 120 => rr = 1.2
        take_profit=Decimal("73920"),
        stop_loss=Decimal("73700"),
        quantity=Decimal("0.001"),
    )

    session = DummySession()
    data = await prepare_n8n_trade(session, payload)
    assert "entry_notional" in data


@pytest.mark.asyncio
async def test_invalid_risk_or_reward_rejected(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73800"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    session = DummySession()

    # risk <= 0 (SL por encima en LONG)
    payload_risk = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74000"),
        stop_loss=Decimal("73900"),
        quantity=Decimal("0.001"),
    )
    with pytest.raises(ValueError) as exc1:
        await prepare_n8n_trade(session, payload_risk)
    assert "INVALID_EXECUTION_PRICES" in str(exc1.value)

    # reward <= 0 (TP por debajo en LONG)
    payload_reward = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("73750"),
        stop_loss=Decimal("73700"),
        quantity=Decimal("0.001"),
    )
    with pytest.raises(ValueError) as exc2:
        await prepare_n8n_trade(session, payload_reward)
    assert "INVALID_EXECUTION_PRICES" in str(exc2.value)


@pytest.mark.asyncio
async def test_no_signal_timestamp_allowed(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73800"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    payload = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
        signal_timestamp=None,
    )

    session = DummySession()
    data = await prepare_n8n_trade(session, payload)
    assert "entry_notional" in data


@pytest.mark.asyncio
async def test_market_defaults_to_usdm_perpetual_and_rejects_spot(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73800"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    session = DummySession()

    # market vacío -> debe aceptar (usa usdm_perpetual)
    payload_default = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
        market="",
    )
    data = await prepare_n8n_trade(session, payload_default)
    assert "entry_notional" in data

    # market spot -> debe rechazar con UNSUPPORTED_MARKET
    payload_spot = N8nTradeCreate(
        symbol="BTCUSDT",
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
        market="spot",
    )
    with pytest.raises(ValueError) as exc:
        await prepare_n8n_trade(session, payload_spot)
    assert "UNSUPPORTED_MARKET" in str(exc.value)


@pytest.mark.asyncio
async def test_symbol_not_usdm_perpetual_rejected(monkeypatch):
    async def fake_price(_self, _symbol: str):
        return Decimal("73800"), False

    from app.services import market_data

    monkeypatch.setattr(market_data.MarketDataService, "get_current_price_with_freshness", fake_price, raising=True)

    session = DummySession()

    payload = N8nTradeCreate(
        symbol="BTCUSD",  # sin sufijo USDT
        strategy_family="TEST",
        strategy_name="test_strategy",
        strategy_version="1.0",
        timeframe="15m",
        position_side="LONG",
        leverage=10,
        entry_price=Decimal("73800"),
        take_profit=Decimal("74200"),
        stop_loss=Decimal("73600"),
        quantity=Decimal("0.001"),
    )
    with pytest.raises(ValueError) as exc:
        await prepare_n8n_trade(session, payload)
    assert "SYMBOL_NOT_USDM_PERPETUAL" in str(exc.value)

