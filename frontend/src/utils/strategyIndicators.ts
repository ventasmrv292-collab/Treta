/**
 * Cálculo de indicadores usados por cada estrategia, para superponer en el gráfico de velas.
 * Coincide con la lógica del backend: breakout (volumen, SMA volumen, máx high), vwap (SMA close), ema_pullback (EMA close).
 */
import type { CandleData } from '../types'

export type StrategyOverlayId = 'breakout' | 'vwap_snapback' | 'ema_pullback'

function sma(values: number[], period: number): number[] {
  const out: number[] = []
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(NaN)
      continue
    }
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += values[j]
    out.push(sum / period)
  }
  return out
}

function ema(values: number[], period: number): number[] {
  const k = 2 / (period + 1)
  const out: number[] = []
  for (let i = 0; i < values.length; i++) {
    if (i === 0) {
      out.push(values[0])
      continue
    }
    if (i < period - 1) {
      const slice = values.slice(0, i + 1)
      const first = slice[0]
      let e = first
      for (let j = 1; j < slice.length; j++) e = slice[j] * k + e * (1 - k)
      out.push(e)
      continue
    }
    const prev = out[i - 1]
    out.push(values[i] * k + prev * (1 - k))
  }
  return out
}

function rollingMaxHigh(candles: CandleData[], lookback: number): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = []
  for (let i = 0; i < candles.length; i++) {
    if (i < lookback) {
      result.push({ time: candles[i].time, value: Math.max(...candles.slice(0, i + 1).map((c) => c.high)) })
      continue
    }
    const window = candles.slice(i - lookback, i)
    const maxHigh = Math.max(...window.map((c) => c.high))
    result.push({ time: candles[i].time, value: maxHigh })
  }
  return result
}

export interface IndicatorSeries {
  id: string
  label: string
  data: { time: number; value: number }[]
  color: string
  /** Si es volumen, se dibuja en escala separada (histogram o línea secundaria) */
  isVolume?: boolean
}

const LOOKBACK_BREAKOUT = 10
const MA_PERIOD_VWAP = 20
const EMA_PERIOD = 20

/** Indicadores para Breakout: volumen (barras), SMA(volumen), máximo reciente de high (nivel de ruptura). */
export function getBreakoutIndicators(candles: CandleData[]): IndicatorSeries[] {
  if (candles.length < LOOKBACK_BREAKOUT) return []
  const volumes = candles.map((c) => c.volume)
  const volSma = sma(volumes, LOOKBACK_BREAKOUT)
  const prevHigh = rollingMaxHigh(candles, LOOKBACK_BREAKOUT)
  return [
    {
      id: 'volume',
      label: 'Volumen',
      data: candles.map((c) => ({ time: c.time, value: c.volume })),
      color: '#64748b',
      isVolume: true,
    },
    {
      id: 'vol_sma',
      label: 'Vol SMA(10)',
      data: candles.map((c, i) => ({ time: c.time, value: volSma[i] })).filter((d) => !Number.isNaN(d.value)),
      color: '#a78bfa',
      isVolume: true,
    },
    {
      id: 'prev_high',
      label: 'Máx High (10)',
      data: prevHigh,
      color: '#f59e0b',
    },
  ]
}

/** Indicadores para VWAP Snapback: SMA(cierre, 20) como proxy de VWAP. */
export function getVwapSnapbackIndicators(candles: CandleData[]): IndicatorSeries[] {
  if (candles.length < MA_PERIOD_VWAP) return []
  const closes = candles.map((c) => c.close)
  const ma = sma(closes, MA_PERIOD_VWAP)
  return [
    {
      id: 'sma20',
      label: 'SMA(20)',
      data: candles.map((c, i) => ({ time: c.time, value: ma[i] })).filter((d) => !Number.isNaN(d.value)),
      color: '#06b6d4',
    },
  ]
}

/** Indicadores para EMA Pullback: EMA(cierre, 20). */
export function getEmaPullbackIndicators(candles: CandleData[]): IndicatorSeries[] {
  if (candles.length < EMA_PERIOD) return []
  const closes = candles.map((c) => c.close)
  const emaValues = ema(closes, EMA_PERIOD)
  return [
    {
      id: 'ema20',
      label: 'EMA(20)',
      data: candles.map((c, i) => ({ time: c.time, value: emaValues[i] })),
      color: '#ec4899',
    },
  ]
}

export function getIndicatorsForStrategy(
  strategy: StrategyOverlayId,
  candles: CandleData[]
): IndicatorSeries[] {
  switch (strategy) {
    case 'breakout':
      return getBreakoutIndicators(candles)
    case 'vwap_snapback':
      return getVwapSnapbackIndicators(candles)
    case 'ema_pullback':
      return getEmaPullbackIndicators(candles)
    default:
      return []
  }
}
