import { useState, useEffect } from 'react'
import { fetchTrades, closeTrade } from '../api/endpoints'
import type { Trade, TradeListResponse } from '../types'
import { format } from 'date-fns'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useToast } from '../components/Toaster'

export function History() {
  const { addToast } = useToast()
  const [data, setData] = useState<TradeListResponse | null>(null)
  const [page, setPage] = useState(1)
  const [closingId, setClosingId] = useState<number | null>(null)
  const [closeForm, setCloseForm] = useState({ exit_price: '', exit_order_type: 'MARKET' as const, maker_taker_exit: 'TAKER' as const, exit_reason: '' })
  const [filters, setFilters] = useState<{
    source?: string
    position_side?: string
    leverage?: number
    closed_only?: boolean
    winners_only?: boolean
    losers_only?: boolean
  }>({})
  const size = 20

  const loadTrades = () => {
    fetchTrades({ page, size, ...filters })
      .then(setData)
      .catch(() => setData(null))
  }
  useEffect(() => {
    loadTrades()
  }, [page, filters.source, filters.position_side, filters.leverage, filters.closed_only, filters.winners_only, filters.losers_only])

  const handleCloseTrade = async () => {
    if (!closingId || !closeForm.exit_price || !closeForm.exit_reason) {
      addToast('Completa precio de salida y motivo', 'error')
      return
    }
    try {
      await closeTrade(closingId, { ...closeForm, closed_at: undefined })
      addToast('Operación cerrada correctamente', 'success')
      setClosingId(null)
      setCloseForm({ exit_price: '', exit_order_type: 'MARKET', maker_taker_exit: 'TAKER', exit_reason: '' })
      loadTrades()
    } catch (e) {
      addToast(e instanceof Error ? e.message : 'Error al cerrar', 'error')
    }
  }

  const trades = data?.items ?? []
  const total = data?.total ?? 0
  const pages = data?.pages ?? 0

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Histórico de operaciones</h2>
      <div className="flex flex-wrap gap-3">
        <select
          value={filters.source ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value || undefined }))}
          className="rounded-lg border border-white/10 bg-[var(--surface-muted)] px-3 py-1.5 text-sm"
        >
          <option value="">Todos (origen)</option>
          <option value="manual">Manual</option>
          <option value="n8n">n8n</option>
        </select>
        <select
          value={filters.position_side ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, position_side: e.target.value || undefined }))}
          className="rounded-lg border border-white/10 bg-[var(--surface-muted)] px-3 py-1.5 text-sm"
        >
          <option value="">Long/Short</option>
          <option value="LONG">Long</option>
          <option value="SHORT">Short</option>
        </select>
        <select
          value={filters.leverage ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, leverage: e.target.value ? Number(e.target.value) : undefined }))}
          className="rounded-lg border border-white/10 bg-[var(--surface-muted)] px-3 py-1.5 text-sm"
        >
          <option value="">Leverage</option>
          <option value="10">x10</option>
          <option value="20">x20</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.closed_only ?? false}
            onChange={(e) => setFilters((f) => ({ ...f, closed_only: e.target.checked || undefined }))}
            className="rounded border-white/20"
          />
          Solo cerradas
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.winners_only ?? false}
            onChange={(e) => setFilters((f) => ({ ...f, winners_only: e.target.checked || undefined }))}
            className="rounded border-white/20"
          />
          Ganadoras
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.losers_only ?? false}
            onChange={(e) => setFilters((f) => ({ ...f, losers_only: e.target.checked || undefined }))}
            className="rounded border-white/20"
          />
          Perdedoras
        </label>
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/10 bg-[var(--surface-muted)]">
        <table className="w-full min-w-[900px] text-sm">
          <thead>
            <tr className="border-b border-white/10 text-left text-[var(--text-muted)]">
              <th className="p-3 font-medium">Fecha</th>
              <th className="p-3 font-medium">Símbolo</th>
              <th className="p-3 font-medium">Origen</th>
              <th className="p-3 font-medium">Estrategia</th>
              <th className="p-3 font-medium">TF</th>
              <th className="p-3 font-medium">L/S</th>
              <th className="p-3 font-medium">Entrada</th>
              <th className="p-3 font-medium">Salida</th>
              <th className="p-3 font-medium">Leverage</th>
              <th className="p-3 font-medium">Qty</th>
              <th className="p-3 font-medium">Fee ent</th>
              <th className="p-3 font-medium">Fee sal</th>
              <th className="p-3 font-medium">PnL neto</th>
              <th className="p-3 font-medium">PnL %</th>
              <th className="p-3 font-medium">Cierre</th>
              <th className="p-3 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 && (
              <tr>
                <td colSpan={16} className="p-8 text-center text-[var(--text-muted)]">
                  No hay operaciones con los filtros actuales.
                </td>
              </tr>
            )}
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-white/5 hover:bg-white/5">
                <td className="p-3">{format(new Date(t.created_at), 'dd/MM/yy HH:mm')}</td>
                <td className="p-3">{t.symbol}</td>
                <td className="p-3">{t.source}</td>
                <td className="p-3">{t.strategy_name}</td>
                <td className="p-3">{t.timeframe}</td>
                <td className="p-3">{t.position_side}</td>
                <td className="p-3">{t.entry_price}</td>
                <td className="p-3">{t.exit_price ?? '—'}</td>
                <td className="p-3">x{t.leverage}</td>
                <td className="p-3">{t.quantity}</td>
                <td className="p-3">{t.entry_fee != null ? parseFloat(t.entry_fee).toFixed(4) : '—'}</td>
                <td className="p-3">{t.exit_fee != null ? parseFloat(t.exit_fee).toFixed(4) : '—'}</td>
                <td className={`p-3 font-medium ${t.net_pnl_usdt != null && parseFloat(t.net_pnl_usdt) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                  {t.net_pnl_usdt != null ? `$${parseFloat(t.net_pnl_usdt).toFixed(2)}` : '—'}
                </td>
                <td className="p-3">{t.pnl_pct_notional != null ? `${parseFloat(t.pnl_pct_notional).toFixed(2)}%` : '—'}</td>
                <td className="p-3">{t.exit_reason ?? '—'}</td>
                <td className="p-3">
                  {!t.closed_at && (
                    <button
                      type="button"
                      onClick={() => { setClosingId(t.id); setCloseForm({ exit_price: '', exit_order_type: 'MARKET', maker_taker_exit: 'TAKER', exit_reason: '' }) }}
                      className="rounded bg-[var(--accent)]/80 px-2 py-1 text-xs font-medium hover:bg-[var(--accent)]"
                    >
                      Cerrar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {closingId != null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">Cerrar operación #{closingId}</h3>
              <button type="button" onClick={() => setClosingId(null)} className="rounded p-1 hover:bg-white/10">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3">
              <label className="block">
                <span className="text-sm text-[var(--text-muted)]">Precio de salida *</span>
                <input
                  type="text"
                  value={closeForm.exit_price}
                  onChange={(e) => setCloseForm((f) => ({ ...f, exit_price: e.target.value }))}
                  className="mt-1 w-full rounded border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--text-muted)]">Tipo orden</span>
                <select
                  value={closeForm.exit_order_type}
                  onChange={(e) => setCloseForm((f) => ({ ...f, exit_order_type: e.target.value as 'MARKET' | 'LIMIT' }))}
                  className="mt-1 w-full rounded border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
                >
                  <option value="MARKET">MARKET</option>
                  <option value="LIMIT">LIMIT</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm text-[var(--text-muted)]">Maker/Taker salida</span>
                <select
                  value={closeForm.maker_taker_exit}
                  onChange={(e) => setCloseForm((f) => ({ ...f, maker_taker_exit: e.target.value as 'MAKER' | 'TAKER' }))}
                  className="mt-1 w-full rounded border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
                >
                  <option value="MAKER">MAKER</option>
                  <option value="TAKER">TAKER</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm text-[var(--text-muted)]">Motivo cierre *</span>
                <input
                  type="text"
                  value={closeForm.exit_reason}
                  onChange={(e) => setCloseForm((f) => ({ ...f, exit_reason: e.target.value }))}
                  placeholder="take_profit, stop_loss, manual..."
                  className="mt-1 w-full rounded border border-white/10 bg-[var(--surface)] px-3 py-2 text-sm"
                />
              </label>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={handleCloseTrade}
                className="rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                Cerrar operación
              </button>
              <button
                type="button"
                onClick={() => setClosingId(null)}
                className="rounded border border-white/20 px-4 py-2 text-sm hover:bg-white/5"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-muted)]">
          Total: {total} operaciones
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-lg border border-white/10 p-2 hover:bg-white/5 disabled:opacity-50"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm">
            Página {page} de {pages || 1}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages}
            className="rounded-lg border border-white/10 p-2 hover:bg-white/5 disabled:opacity-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
