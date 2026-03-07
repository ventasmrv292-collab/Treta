/**
 * Módulo compartido: fees, PnL, margen y validación de capital.
 * Reglas: entry_notional = quantity * entry_price, margin_used = entry_notional / leverage
 */

export type MakerTaker = "MAKER" | "TAKER";
export type PositionSide = "LONG" | "SHORT";

export interface FeeConfigRow {
  maker_fee_bps: number;
  taker_fee_bps: number;
  bnb_discount_pct: number;
  default_slippage_bps: number;
  include_funding: boolean;
}

export function getFeeRate(
  makerFeeBps: number,
  takerFeeBps: number,
  makerTaker: MakerTaker,
  bnbDiscountPct: number = 0
): number {
  const bps = makerTaker === "TAKER" ? takerFeeBps : makerFeeBps;
  let rate = bps / 10000;
  if (bnbDiscountPct) rate *= 1 - bnbDiscountPct / 100;
  return Math.round(rate * 1e8) / 1e8;
}

export function calcEntryFee(entryNotional: number, feeRate: number): number {
  return Math.round(entryNotional * feeRate * 10000) / 10000;
}

export function calcExitFee(exitNotional: number, feeRate: number): number {
  return Math.round(exitNotional * feeRate * 10000) / 10000;
}

export function calcGrossPnl(
  positionSide: PositionSide,
  entryPrice: number,
  exitPrice: number,
  quantity: number
): number {
  if (positionSide === "LONG") {
    return Math.round((exitPrice - entryPrice) * quantity * 10000) / 10000;
  }
  return Math.round((entryPrice - exitPrice) * quantity * 10000) / 10000;
}

export function calcNetPnl(
  grossPnlUsdt: number,
  entryFee: number,
  exitFee: number,
  fundingFee: number = 0,
  slippageUsdt: number = 0
): number {
  return Math.round((grossPnlUsdt - entryFee - exitFee - fundingFee - slippageUsdt) * 10000) / 10000;
}

export function calcMarginUsed(entryNotional: number, leverage: number): number {
  if (leverage <= 0) return 0;
  return Math.round((entryNotional / leverage) * 10000) / 10000;
}

export function calcSlippageUsdt(
  entryNotional: number,
  exitNotional: number,
  slippageBps: number
): number {
  const slip = slippageBps / 10000;
  return Math.round((entryNotional + exitNotional) * slip * 10000) / 10000;
}

export function validateAvailableCapital(
  availableBalanceUsdt: number,
  marginUsedUsdt: number,
  entryFee: number
): { ok: boolean; reason?: string } {
  const required = marginUsedUsdt + entryFee;
  if (availableBalanceUsdt < required) {
    return {
      ok: false,
      reason: `Capital insuficiente: disponible ${availableBalanceUsdt}, necesario ${required} (margen ${marginUsedUsdt} + fee entrada ${entryFee})`,
    };
  }
  return { ok: true };
}

export function computeFeesAndPnl(
  quantity: number,
  entryPrice: number,
  exitPrice: number,
  positionSide: PositionSide,
  makerTakerEntry: MakerTaker,
  makerTakerExit: MakerTaker,
  feeConfig: FeeConfigRow,
  slippageBps?: number,
  fundingFee: number = 0
): {
  entryNotional: number;
  exitNotional: number;
  entryFee: number;
  exitFee: number;
  grossPnlUsdt: number;
  netPnlUsdt: number;
  slippageUsdt: number;
} {
  const entryNotional = Math.round(quantity * entryPrice * 10000) / 10000;
  const exitNotional = Math.round(quantity * exitPrice * 10000) / 10000;
  const slipBps = slippageBps ?? feeConfig.default_slippage_bps;
  const slippageUsdt = calcSlippageUsdt(entryNotional, exitNotional, slipBps);

  const entryRate = getFeeRate(
    feeConfig.maker_fee_bps,
    feeConfig.taker_fee_bps,
    makerTakerEntry,
    feeConfig.bnb_discount_pct
  );
  const exitRate = getFeeRate(
    feeConfig.maker_fee_bps,
    feeConfig.taker_fee_bps,
    makerTakerExit,
    feeConfig.bnb_discount_pct
  );
  const entryFee = calcEntryFee(entryNotional, entryRate);
  const exitFee = calcExitFee(exitNotional, exitRate);
  const funding = feeConfig.include_funding ? fundingFee : 0;
  const grossPnlUsdt = calcGrossPnl(positionSide, entryPrice, exitPrice, quantity);
  const netPnlUsdt = calcNetPnl(grossPnlUsdt, entryFee, exitFee, funding, slippageUsdt);

  return {
    entryNotional,
    exitNotional,
    entryFee,
    exitFee,
    grossPnlUsdt,
    netPnlUsdt,
    slippageUsdt,
  };
}
