import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchStrategies, fetchPaperAccounts, createTrade, fetchRiskProfiles, fetchPositionSizePreview } from '../api/endpoints'
import { useToast } from '../components/Toaster'
import type { Strategy, PaperAccount, RiskProfile, PositionSizePreview } from '../types'
import type { ManualTradeCreate } from '../types'

const TIMEFRAMES = ['15m', '30m', '1h']
const LEVERAGE_OPTIONS = [10, 20]
const POSITION_SIDES = ['LONG', 'SHORT'] as const
const ORDER_TYPES = ['MARKET', 'LIMIT']
const MAKER_TAKER = ['MAKER', 'TAKER']

export function NewTrade() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [paperAccounts, setPaperAccounts] = useState<PaperAccount[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState<ManualTradeCreate & { risk_profile_id?: number | null }>({
    source: 'manual',
    symbol: 'BTCUSDT',
    market: 'usdt_m',
    strategy_family: '',
    strategy_name: '',
    strategy_version: '1.0',
    timeframe: '15m',
    position_side: 'LONG',
    order_side_entry: 'BUY',
    order_type_entry: 'MARKET',
    maker_taker_entry: 'TAKER',
    leverage: 10,
    quantity: '',
    entry_price: '',
    take_profit: '',
    stop_loss: '',
    notes: '',
  })
  const [riskProfiles, setRiskProfiles] = useState<RiskProfile[]>([])
  const [sizingPreview, setSizingPreview] = useState<PositionSizePreview | null>(null)

  useEffect(() => {
    fetchStrategies().then(setStrategies).catch(() => addToast('Error cargando estrategias', 'error'))
    fetchPaperAccounts()
      .then((accs) => {
        setPaperAccounts(accs)
        const activeAccount = accs.find((a) => a.status === 'ACTIVE')
        const accountId = activeAccount?.id ?? (accs.length > 0 ? accs[0].id : null)
        if (accountId != null) setSelectedAccountId(accountId)
      })
      .catch(() => {})
    fetchRiskProfiles().then(setRiskProfiles).catch(() => {})
  }, [addToast])

  const selectedProfileId = form.risk_profile_id ?? null
  const loadSizingPreview = useCallback(() => {
    if (!selectedProfileId || !form.entry_price || parseFloat(form.entry_price) <= 0) {
      setSizingPreview(null)
      return
    }
    const needStop = riskProfiles.find((p) => p.id === selectedProfileId)?.sizing_mode === 'RISK_PCT_OF_EQUITY'
    if (needStop && (!form.stop_loss || parseFloat(form.stop_loss) <= 0)) {
      setSizingPreview(null)
      return
    }
    fetchPositionSizePreview(selectedProfileId, {
      entry_price: form.entry_price,
      leverage: form.leverage,
      stop_loss: form.stop_loss || undefined,
      position_side: form.position_side,
      account_id: selectedAccountId ?? undefined,
    })
      .then(setSizingPreview)
      .catch(() => setSizingPreview(null))
  }, [selectedProfileId, form.entry_price, form.leverage, form.stop_loss, form.position_side, selectedAccountId, riskProfiles])

  useEffect(() => {
    loadSizingPreview()
  }, [loadSizingPreview])

  useEffect(() => {
    const s = strategies.find((x) => `${x.family}/${x.name}` === `${form.strategy_family}/${form.strategy_name}`)
    if (s) {
      setForm((f) => ({ ...f, strategy_family: s.family, strategy_name: s.name, strategy_version: s.version }))
    }
  }, [form.strategy_name, form.strategy_family, strategies])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.quantity || !form.entry_price) {
      addToast('Completa cantidad y precio de entrada', 'error')
      return
    }
    if (!form.strategy_family || !form.strategy_name) {
      addToast('Selecciona estrategia', 'error')
      return
    }
    const acc = paperAccounts.find((a) => a.id === selectedAccountId)
    if (acc && selectedAccountId != null) {
      const n = parseFloat(form.quantity) * parseFloat(form.entry_price)
      const margin = form.leverage ? n / form.leverage : 0
      const fee = n * 0.0004
      if (parseFloat(acc.available_balance_usdt) < margin + fee) {
        addToast('Capital insuficiente en la cuenta paper', 'error')
        return
      }
    }
    setLoading(true)
    try {
      const payload: ManualTradeCreate & { risk_profile_id?: number | null } = {
        ...form,
        order_side_entry: form.position_side === 'LONG' ? 'BUY' : 'SELL',
        take_profit: form.take_profit || undefined,
        stop_loss: form.stop_loss || undefined,
        ...(selectedAccountId != null && { account_id: selectedAccountId }),
        ...(form.risk_profile_id != null && { risk_profile_id: form.risk_profile_id }),
      }
      await createTrade(payload)
      addToast('Operación registrada correctamente', 'success')
      navigate('/history')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Error al guardar', 'error')
    } finally {
      setLoading(false)
    }
  }

  const strategyFamilies = [...new Set(strategies.map((s) => s.family))]
  const strategyNames = strategies.filter((s) => s.family === form.strategy_family)

  const qty = parseFloat(form.quantity) || 0
  const entryPrice = parseFloat(form.entry_price) || 0
  const entryNotional = qty * entryPrice
  const marginUsed = form.leverage ? entryNotional / form.leverage : 0
  const entryFeeRate = 0.0004
  const entryFee = entryNotional * entryFeeRate
  const selectedAccount = paperAccounts.find((a) => a.id === selectedAccountId)
  const availableAfter = selectedAccount ? parseFloat(selectedAccount.available_balance_usdt) - marginUsed - entryFee : 0

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-xl font-semibold">Nueva operación manual</h2>
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Símbolo</span>
            <input
              type="text"
              value={form.symbol}
              onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Mercado</span>
            <input
              type="text"
              value={form.market}
              readOnly
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm opacity-80"
            />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Familia estrategia</span>
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
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Estrategia</span>
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
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Versión</span>
            <input
              type="text"
              value={form.strategy_version}
              onChange={(e) => setForm((f) => ({ ...f, strategy_version: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Timeframe</span>
            <select
              value={form.timeframe}
              onChange={(e) => setForm((f) => ({ ...f, timeframe: e.target.value }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Lado</span>
            <select
              value={form.position_side}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  position_side: e.target.value as 'LONG' | 'SHORT',
                  order_side_entry: e.target.value === 'LONG' ? 'BUY' : 'SELL',
                }))
              }
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              {POSITION_SIDES.map((ps) => (
                <option key={ps} value={ps}>{ps}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Tipo orden entrada</span>
            <select
              value={form.order_type_entry}
              onChange={(e) => setForm((f) => ({ ...f, order_type_entry: e.target.value as 'MARKET' | 'LIMIT' }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              {ORDER_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Maker/Taker entrada</span>
            <select
              value={form.maker_taker_entry}
              onChange={(e) => setForm((f) => ({ ...f, maker_taker_entry: e.target.value as 'MAKER' | 'TAKER' }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              {MAKER_TAKER.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Apalancamiento</span>
            <select
              value={form.leverage}
              onChange={(e) => setForm((f) => ({ ...f, leverage: Number(e.target.value) }))}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              {LEVERAGE_OPTIONS.map((lev) => (
                <option key={lev} value={lev}>x{lev}</option>
              ))}
            </select>
          </label>
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Perfil de riesgo (opcional)</span>
            <select
              value={form.risk_profile_id ?? ''}
              onChange={(e) => {
                const v = e.target.value
                setForm((f) => ({ ...f, risk_profile_id: v ? Number(v) : null }))
              }}
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            >
              <option value="">Sin perfil (cantidad manual)</option>
              {riskProfiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.sizing_mode})</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Cantidad</span>
            <input
              type="text"
              inputMode="decimal"
              value={form.quantity}
              onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
              placeholder="0.001"
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Precio entrada *</span>
            <input
              type="text"
              inputMode="decimal"
              value={form.entry_price}
              onChange={(e) => setForm((f) => ({ ...f, entry_price: e.target.value }))}
              placeholder="67000"
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-[var(--text-muted)]">Take profit</span>
            <input
              type="text"
              inputMode="decimal"
              value={form.take_profit}
              onChange={(e) => setForm((f) => ({ ...f, take_profit: e.target.value || undefined }))}
              placeholder="Opcional"
              className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
            />
          </label>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm text-[var(--text-muted)]">Stop loss</span>
          <input
            type="text"
            inputMode="decimal"
            value={form.stop_loss}
            onChange={(e) => setForm((f) => ({ ...f, stop_loss: e.target.value || undefined }))}
            placeholder="Opcional"
            className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-[var(--text-muted)]">Notas</span>
          <textarea
            value={form.notes ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value || undefined }))}
            rows={2}
            className="w-full rounded-lg border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
          />
        </label>
        {sizingPreview && (
          <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-4">
            <p className="mb-2 text-sm font-medium text-[var(--text-muted)]">Preview por perfil de riesgo</p>
            <ul className="space-y-1 text-sm">
              <li>Cantidad calculada: {sizingPreview.quantity}</li>
              <li>Notional: ${parseFloat(sizingPreview.entry_notional).toFixed(2)}</li>
              <li>Margen usado: ${parseFloat(sizingPreview.margin_used_usdt).toFixed(2)}</li>
              <li>Fee entrada (est.): ${parseFloat(sizingPreview.entry_fee_estimate).toFixed(2)}</li>
              {sizingPreview.estimated_loss_to_sl_usdt != null && (
                <li className="text-amber-400">Pérdida estimada hasta SL: ${parseFloat(sizingPreview.estimated_loss_to_sl_usdt).toFixed(2)}</li>
              )}
            </ul>
          </div>
        )}
        {qty > 0 && entryPrice > 0 && (
          <div className="rounded-lg border border-white/10 bg-black/20 p-4">
            <p className="mb-2 text-sm font-medium text-[var(--text-muted)]">Preview</p>
            <ul className="space-y-1 text-sm">
              <li>Notional: ${entryNotional.toFixed(2)}</li>
              <li>Margen usado: ${marginUsed.toFixed(2)}</li>
              <li>Fee entrada (aprox.): ${entryFee.toFixed(2)}</li>
              {selectedAccount && (
                <li className={availableAfter < 0 ? 'text-red-400' : ''}>
                  Capital disponible después: ${availableAfter.toFixed(2)}
                </li>
              )}
            </ul>
          </div>
        )}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Guardando...' : 'Registrar operación'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="rounded-lg border border-white/20 px-4 py-2 font-medium hover:bg-white/5"
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  )
}
