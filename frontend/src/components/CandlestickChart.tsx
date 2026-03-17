import { useEffect, useRef, useCallback, useState } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickData } from 'lightweight-charts'
import type { CandleData } from '../types'
import { getIndicatorsForStrategy, type StrategyOverlayId } from '../utils/strategyIndicators'

interface CandlestickChartProps {
  data: CandleData[]
  height?: number
  interval?: string
  onCrosshairMove?: (price: number | null) => void
  /** Precio en vivo para actualizar la última vela en tiempo real */
  livePrice?: number | null
  /** Estrategia cuyos indicadores se superponen en el gráfico (Breakout, VWAP, EMA) */
  strategyOverlay?: StrategyOverlayId | null
  /** Nombre del indicador (para tooltip al pasar el ratón por las líneas) */
  indicatorName?: string
  /** Descripción breve del indicador (para tooltip) */
  indicatorDescription?: string
}

export function CandlestickChart({ data, height = 400, interval = '15m', onCrosshairMove, livePrice, strategyOverlay, indicatorName, indicatorDescription }: CandlestickChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const indicatorSeriesRef = useRef<ISeriesApi<'Line'>[]>([])
  const indicatorNameRef = useRef<string | undefined>(indicatorName)
  const indicatorDescRef = useRef<string | undefined>(indicatorDescription)
  indicatorNameRef.current = indicatorName
  indicatorDescRef.current = indicatorDescription
  /** Posición del tooltip cuando el ratón está sobre una línea de indicador (coords relativas al contenedor). */
  const [indicatorTooltip, setIndicatorTooltip] = useState<{ x: number; y: number } | null>(null)

  const isDark = !document.documentElement.classList.contains('light')

  useEffect(() => {
    if (!chartRef.current || !data.length) return
    const chart = createChart(chartRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: isDark ? '#94a3b8' : '#64748b',
      },
      grid: {
        vertLines: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' },
        horzLines: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' },
      },
      rightPriceScale: {
        borderColor: isDark ? '#334155' : '#e2e8f0',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: isDark ? '#334155' : '#e2e8f0',
        timeVisible: true,
        secondsVisible: false,
      },
    })
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      wickUpColor: '#22c55e',
    })
    const chartData: CandlestickData[] = data.map((c) => ({
      time: c.time as unknown as CandlestickData['time'],
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    candlestickSeries.setData(chartData)
    chart.timeScale().fitContent()
    chartInstance.current = chart
    seriesRef.current = candlestickSeries

    chart.subscribeCrosshairMove((param) => {
      if (onCrosshairMove) {
        const price = param.seriesData.get(candlestickSeries) as { close?: number } | undefined
        onCrosshairMove(price?.close ?? null)
      }
      const indicators = indicatorSeriesRef.current
      const overIndicator = indicators.length > 0 && indicators.some((s) => param.seriesData.get(s) != null)
      const point = param.point as { x: number; y: number } | undefined
      if (overIndicator && point != null && indicatorNameRef.current && indicatorDescRef.current) {
        setIndicatorTooltip((prev) => (prev && prev.x === point.x && prev.y === point.y ? prev : { x: point.x, y: point.y }))
      } else {
        setIndicatorTooltip(null)
      }
    })
    return () => {
      chart.remove()
      chartInstance.current = null
      seriesRef.current = null
    }
  }, [data.length, isDark, onCrosshairMove])

  const updateData = useCallback((newData: CandleData[]) => {
    if (!seriesRef.current || !newData.length) return
    const chartData: CandlestickData[] = newData.map((c) => ({
      time: c.time as unknown as CandlestickData['time'],
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    chartData.forEach((d) => seriesRef.current!.update(d))
  }, [])

  useEffect(() => {
    if (data.length && seriesRef.current) {
      const chartData: CandlestickData[] = data.map((c) => ({
        time: c.time as unknown as CandlestickData['time'],
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      seriesRef.current.setData(chartData)
      chartInstance.current?.timeScale().fitContent()
    }
  }, [data])

  // Precio en vivo: actualizar solo la última vela para que el gráfico se mueva en tiempo real
  useEffect(() => {
    if (livePrice == null || !data.length || !seriesRef.current) return
    const last = data[data.length - 1]
    const high = Math.max(last.high, livePrice)
    const low = Math.min(last.low, livePrice)
    seriesRef.current.update({
      time: last.time as unknown as CandlestickData['time'],
      open: last.open,
      high,
      low,
      close: livePrice,
    })
  }, [livePrice, data])

  // Indicadores por estrategia: añadir o quitar series de líneas + tooltip al pasar el ratón
  useEffect(() => {
    const chart = chartInstance.current
    if (!chart || !data.length) return

    indicatorSeriesRef.current.forEach((s) => {
      try {
        chart.removeSeries(s)
      } catch (_) {}
    })
    indicatorSeriesRef.current = []

    if (strategyOverlay) {
      const seriesList = getIndicatorsForStrategy(strategyOverlay, data)
      const timeData = (arr: { time: number; value: number }[]) =>
        arr.map((d) => ({ time: d.time as unknown as CandlestickData['time'], value: d.value }))

      seriesList.forEach((ind) => {
        const options: { color: string; priceScaleId?: string } = { color: ind.color }
        if (ind.isVolume) {
          options.priceScaleId = 'volume'
        }
        const lineSeries = chart.addLineSeries(options)
        if (ind.isVolume) {
          try {
            lineSeries.priceScale().applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } })
          } catch (_) {}
        }
        lineSeries.setData(timeData(ind.data))
        indicatorSeriesRef.current.push(lineSeries)
      })
      chart.timeScale().fitContent()
    } else {
      setIndicatorTooltip(null)
    }
  }, [data, strategyOverlay])

  return (
    <div className="relative" style={{ height: `${height}px`, width: '100%' }}>
      <div ref={chartRef} className="absolute inset-0" style={{ height: `${height}px`, width: '100%' }} />
      {indicatorTooltip != null && indicatorName && indicatorDescription && (
        <div
          className="pointer-events-none absolute z-10 max-w-[240px] rounded-lg border border-white/20 bg-slate-900/95 px-2.5 py-2 text-left text-xs shadow-lg backdrop-blur"
          style={{
            left: indicatorTooltip.x + 12,
            top: indicatorTooltip.y - 8,
          }}
        >
          <p className="font-semibold text-[var(--accent)]">{indicatorName}</p>
          <p className="mt-0.5 text-[var(--text-muted)]">{indicatorDescription}</p>
        </div>
      )}
    </div>
  )
}
