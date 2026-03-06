import { useEffect, useRef, useCallback } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickData } from 'lightweight-charts'
import type { CandleData } from '../types'

interface CandlestickChartProps {
  data: CandleData[]
  height?: number
  interval?: string
  onCrosshairMove?: (price: number | null) => void
}

export function CandlestickChart({ data, height = 400, interval = '15m', onCrosshairMove }: CandlestickChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

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

    if (onCrosshairMove) {
      chart.subscribeCrosshairMove((param) => {
        const price = param.seriesData.get(candlestickSeries) as { close?: number } | undefined
        onCrosshairMove(price?.close ?? null)
      })
    }
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

  return <div ref={chartRef} style={{ height: `${height}px`, width: '100%' }} />
}
