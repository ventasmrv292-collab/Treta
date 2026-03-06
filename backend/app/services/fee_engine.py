"""Fee and PnL simulation engine for Binance Futures."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class FeeProfile(str, Enum):
    CONSERVATIVE = "conservative"  # higher fees
    REALISTIC = "realistic"       # Binance-like
    OPTIMISTIC = "optimistic"     # lower fees


# Default fee configs (basis points). Binance USD-M: maker ~2bps, taker ~4bps
DEFAULT_FEES: dict[FeeProfile, tuple[float, float, float]] = {
    FeeProfile.CONSERVATIVE: (3.0, 5.0, 0),   # maker_bps, taker_bps, bnb_discount_pct
    FeeProfile.REALISTIC: (2.0, 4.0, 10),     # 10% BNB discount
    FeeProfile.OPTIMISTIC: (1.5, 3.0, 25),
}


@dataclass
class FeeConfigValues:
    maker_fee_bps: float
    taker_fee_bps: float
    bnb_discount_pct: float
    slippage_bps: float
    include_funding: bool = True

    def maker_rate(self) -> Decimal:
        rate = Decimal(str(self.maker_fee_bps)) / Decimal("10000")
        if self.bnb_discount_pct:
            rate *= Decimal("1") - Decimal(str(self.bnb_discount_pct)) / Decimal("100")
        return rate

    def taker_rate(self) -> Decimal:
        rate = Decimal(str(self.taker_fee_bps)) / Decimal("10000")
        if self.bnb_discount_pct:
            rate *= Decimal("1") - Decimal(str(self.bnb_discount_pct)) / Decimal("100")
        return rate


@dataclass
class TradeFeesResult:
    entry_notional: Decimal
    exit_notional: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    funding_fee: Decimal
    slippage_usdt: Decimal
    gross_pnl_usdt: Decimal
    net_pnl_usdt: Decimal
    pnl_pct_notional: Decimal
    pnl_pct_margin: Decimal


class FeeEngine:
    """Calculates fees and PnL for simulated futures trades."""

    def __init__(
        self,
        maker_fee_bps: float = 2.0,
        taker_fee_bps: float = 4.0,
        bnb_discount_pct: float = 10.0,
        default_slippage_bps: float = 0.0,
        include_funding: bool = True,
    ):
        self.config = FeeConfigValues(
            maker_fee_bps=maker_fee_bps,
            taker_fee_bps=taker_fee_bps,
            bnb_discount_pct=bnb_discount_pct,
            slippage_bps=default_slippage_bps,
            include_funding=include_funding,
        )

    @classmethod
    def from_profile(cls, profile: FeeProfile, slippage_bps: float = 0.0) -> "FeeEngine":
        maker, taker, bnb = DEFAULT_FEES.get(profile, DEFAULT_FEES[FeeProfile.REALISTIC])
        return cls(
            maker_fee_bps=maker,
            taker_fee_bps=taker,
            bnb_discount_pct=bnb,
            default_slippage_bps=slippage_bps,
        )

    def compute_fees_and_pnl(
        self,
        quantity: Decimal,
        entry_price: Decimal,
        exit_price: Decimal,
        position_side: str,  # LONG, SHORT
        maker_taker_entry: str,  # MAKER, TAKER
        maker_taker_exit: str,
        leverage: int,
        slippage_bps: float | None = None,
        funding_fee: Decimal | None = None,
    ) -> TradeFeesResult:
        """Compute notional, fees, slippage and PnL for a closed trade."""
        slip = Decimal(str(slippage_bps or self.config.slippage_bps)) / Decimal("10000")
        entry_notional = quantity * entry_price
        exit_notional = quantity * exit_price

        # Slippage: apply to both entry and exit (simplified: half each or full on exit)
        slippage_usdt = (entry_notional + exit_notional) * slip

        entry_rate = self.config.taker_rate() if maker_taker_entry == "TAKER" else self.config.maker_rate()
        exit_rate = self.config.taker_rate() if maker_taker_exit == "TAKER" else self.config.maker_rate()
        entry_fee = entry_notional * entry_rate
        exit_fee = exit_notional * exit_rate
        funding = funding_fee or Decimal("0")
        if not self.config.include_funding:
            funding = Decimal("0")

        # Gross PnL: LONG = (exit - entry) * qty, SHORT = (entry - exit) * qty
        if position_side == "LONG":
            gross_pnl_usdt = (exit_price - entry_price) * quantity
        else:
            gross_pnl_usdt = (entry_price - exit_price) * quantity

        total_fees = entry_fee + exit_fee + funding
        net_pnl_usdt = gross_pnl_usdt - total_fees - slippage_usdt

        margin = entry_notional / leverage
        pnl_pct_notional = (net_pnl_usdt / entry_notional * 100) if entry_notional else Decimal("0")
        pnl_pct_margin = (net_pnl_usdt / margin * 100) if margin else Decimal("0")

        return TradeFeesResult(
            entry_notional=entry_notional,
            exit_notional=exit_notional,
            entry_fee=entry_fee,
            exit_fee=exit_fee,
            funding_fee=funding,
            slippage_usdt=slippage_usdt,
            gross_pnl_usdt=gross_pnl_usdt,
            net_pnl_usdt=net_pnl_usdt,
            pnl_pct_notional=pnl_pct_notional,
            pnl_pct_margin=pnl_pct_margin,
        )
