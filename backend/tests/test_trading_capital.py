"""Tests for trading_capital module (cap_quantity_to_limits, validate_can_open_trade)."""
from decimal import Decimal

import pytest

from app.services.trading_capital import cap_quantity_to_limits, validate_can_open_trade


def test_cap_quantity_to_limits_respects_max_notional_usdt():
    """When max_notional_usdt is 800, quantity is capped so entry_notional <= 800."""
    qty = Decimal("0.1")
    entry_price = Decimal("100000")  # notional 10000
    equity = Decimal("5000")
    capped = cap_quantity_to_limits(
        qty,
        entry_price,
        leverage=10,
        equity=equity,
        max_notional_usdt=Decimal("800"),
        max_notional_pct_of_equity=Decimal("90"),
        max_margin_pct_of_equity=Decimal("12"),
    )
    assert capped <= qty
    notional_capped = capped * entry_price
    assert notional_capped <= Decimal("800")


def test_cap_quantity_to_limits_respects_margin_pct():
    """When max_margin_pct is 12%, margin = notional/leverage <= equity * 0.12."""
    qty = Decimal("0.01")
    entry_price = Decimal("50000")
    equity = Decimal("1000")
    leverage = 10
    capped = cap_quantity_to_limits(
        qty,
        entry_price,
        leverage=leverage,
        equity=equity,
        max_notional_usdt=None,
        max_notional_pct_of_equity=Decimal("100"),
        max_margin_pct_of_equity=Decimal("12"),
    )
    margin = (capped * entry_price) / leverage
    assert margin <= equity * Decimal("0.12")


def test_cap_quantity_returns_original_when_within_limits():
    """When no limits are set (None), original quantity is returned."""
    qty = Decimal("0.001")
    capped = cap_quantity_to_limits(
        qty,
        Decimal("60000"),
        leverage=10,
        equity=Decimal("1000"),
        max_notional_usdt=None,
        max_notional_pct_of_equity=None,
        max_margin_pct_of_equity=None,
    )
    assert capped == qty


def test_validate_can_open_trade_insufficient():
    """Rejects when available balance < margin + entry_fee."""
    ok, msg = validate_can_open_trade(
        available_balance_usdt=Decimal("50"),
        margin_used_usdt=Decimal("100"),
        entry_fee=Decimal("1"),
    )
    assert ok is False
    assert "Capital insuficiente" in msg or "insuficiente" in msg


def test_validate_can_open_trade_ok():
    """Accepts when available >= margin + fee."""
    ok, msg = validate_can_open_trade(
        available_balance_usdt=Decimal("200"),
        margin_used_usdt=Decimal("100"),
        entry_fee=Decimal("1"),
    )
    assert ok is True
    assert msg == ""
