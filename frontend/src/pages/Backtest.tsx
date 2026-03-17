import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import { fetchStrategies, runBacktest } from '../api/endpoints'
import { useToast } from '../components/Toaster'
import { useI18n } from '../contexts/I18nContext'
import type { Strategy } from '../types'
import type { BacktestRun } from '../types'
import { format } from 'date-fns'
import { Play } from 'lucide-react'

export function Backtest() {
  const { t } = useI18n()
  const { addToast } = useToast()
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [runs, setRuns] = useState<BacktestRun[]>([])
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    strategy_family: '',
    strategy_name: '',
    strategy_version: '1.0',
    symbol: 'BTCUSDT',
    interval: '15m',
    start_time: '',
    end_time: '',
    initial_capital: '10000',
    leverage: 10,
    fee_profile: 'realistic',
    slippage_bps: 0,
  })

  useEffect(() => {
    fetchStrategies().then(setStrategies).catch(() => {})
  }, [])

  useEffect(() => {
    api.get<BacktestRun[]>(endpoints.backtest.list()).then(setRuns).catch(() => setRuns([]))
  }, [])

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.start_time || !form.end_time) {
      addToast(t('backtest.toastDates'), 'error')
      return
    }
    if (!form.strategy_family || !form.strategy_name) {
      addToast(t('backtest.toastStrategy'), 'error')
      return
    }
    setLoading(true)
    try {
      const run = await runBacktest({
        strategy_family: form.strategy_family,
        strategy_name: form.strategy_name,
        strategy_version: form.strategy_version,
        symbol: form.symbol,
        interval: form.interval,
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        initial_capital: form.initial_capital,
        leverage: form.leverage,
        fee_profile: form.fee_profile,
        slippage_bps: form.slippage_bps,
      })
      setRuns((prev) => [run, ...prev])
      addToast(t('backtest.toastDone'), 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : t('backtest.toastError'), 'error')
    } finally {
      setLoading(false)
    }
  }

  const strategyFamilies = [...new Set(strategies.map((s) => s.family))]
  const strategyNames = strategies.filter((s) => s.family === form.strategy_family)

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold">{t('backtest.title')}</h2>

      <form onSubmit={handleRun} className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 text-sm font-semibold text-[var(--text-muted)]">{t('backtest.newBacktest')}</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.family')}</span>
            <select
              value={form.strategy_family}
              onChange={(e) => setForm((f) => ({ ...f, strategy_family: e.target.value, strategy_name: '' }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              <option value="">—</option>
              {strategyFamilies.map((fam) => (
                <option key={fam} value={fam}>{fam}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.strategy')}</span>
            <select
              value={form.strategy_name}
              onChange={(e) => {
                const s = strategies.find((x) => x.name === e.target.value)
                setForm((f) => ({ ...f, strategy_name: e.target.value, strategy_version: s?.version ?? '1.0' }))
              }}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              <option value="">—</option>
              {strategyNames.map((s) => (
                <option key={s.id} value={s.name}>{s.name}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.interval')}</span>
            <select
              value={form.interval}
              onChange={(e) => setForm((f) => ({ ...f, interval: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              <option value="15m">15m</option>
              <option value="30m">30m</option>
              <option value="1h">1h</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.startTime')}</span>
            <input
              type="datetime-local"
              value={form.start_time}
              onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.endTime')}</span>
            <input
              type="datetime-local"
              value={form.end_time}
              onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.initialCapital')}</span>
            <input
              type="text"
              value={form.initial_capital}
              onChange={(e) => setForm((f) => ({ ...f, initial_capital: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.leverage')}</span>
            <select
              value={form.leverage}
              onChange={(e) => setForm((f) => ({ ...f, leverage: Number(e.target.value) }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              <option value="10">x10</option>
              <option value="20">x20</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">{t('backtest.feeProfile')}</span>
            <select
              value={form.fee_profile}
              onChange={(e) => setForm((f) => ({ ...f, fee_profile: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              <option value="conservative">{t('backtest.conservative')}</option>
              <option value="realistic">{t('backtest.realistic')}</option>
              <option value="optimistic">{t('backtest.optimistic')}</option>
            </select>
          </label>
        </div>
        <div className="mt-4">
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            {loading ? t('backtest.running') : t('backtest.run')}
          </button>
        </div>
      </form>

      <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 text-sm font-semibold text-[var(--text-muted)]">{t('backtest.recentResults')}</h3>
        {runs.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">{t('backtest.noBacktestsYet')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="pb-2 font-medium">{t('backtest.date')}</th>
                  <th className="pb-2 font-medium">{t('backtest.strategy')}</th>
                  <th className="pb-2 font-medium">{t('backtest.interval')}</th>
                  <th className="pb-2 font-medium">{t('backtest.leverage')}</th>
                  <th className="pb-2 font-medium">{t('backtest.capitalInit')}</th>
                  <th className="pb-2 font-medium">{t('backtest.capitalEnd')}</th>
                  <th className="pb-2 font-medium">{t('backtest.returnPct')}</th>
                  <th className="pb-2 font-medium">{t('backtest.peakEquity')}</th>
                  <th className="pb-2 font-medium">{t('backtest.drawdown')}</th>
                  <th className="pb-2 font-medium">{t('backtest.status')}</th>
                  <th className="pb-2 font-medium">{t('backtest.trades')}</th>
                  <th className="pb-2 font-medium">{t('backtest.netPnl')}</th>
                  <th className="pb-2 font-medium">{t('backtest.winRate')}</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const init = parseFloat(r.initial_capital)
                  const final = r.final_capital != null ? parseFloat(r.final_capital) : null
                  const returnPct = init > 0 && final != null ? (((final - init) / init) * 100) : null
                  const peak = r.peak_equity != null ? parseFloat(r.peak_equity) : null
                  const drawdown = r.max_drawdown_pct != null ? r.max_drawdown_pct : null
                  return (
                    <tr key={r.id} className="border-t border-white/5">
                      <td className="py-2">{format(new Date(r.created_at), 'dd/MM/yy HH:mm')}</td>
                      <td className="py-2">{r.strategy_name}</td>
                      <td className="py-2">{r.interval}</td>
                      <td className="py-2">x{r.leverage}</td>
                      <td className="py-2">${init.toFixed(2)}</td>
                      <td className="py-2">{final != null ? `$${final.toFixed(2)}` : '—'}</td>
                      <td className={`py-2 ${returnPct != null ? (returnPct >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]') : ''}`}>
                        {returnPct != null ? `${returnPct.toFixed(2)}%` : '—'}
                      </td>
                      <td className="py-2">{peak != null ? `$${peak.toFixed(2)}` : '—'}</td>
                      <td className="py-2">{drawdown != null ? `${drawdown.toFixed(2)}%` : '—'}</td>
                      <td className="py-2">{r.status}</td>
                      <td className="py-2">{r.total_trades ?? '—'}</td>
                      <td className={`py-2 font-medium ${r.net_pnl != null && parseFloat(r.net_pnl) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                        {r.net_pnl != null ? `$${parseFloat(r.net_pnl).toFixed(2)}` : '—'}
                      </td>
                      <td className="py-2">{r.win_rate != null ? `${r.win_rate.toFixed(1)}%` : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
