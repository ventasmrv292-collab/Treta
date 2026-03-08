import { getEventExplanation } from '../constants/eventExplanations'
import { X } from 'lucide-react'

interface EventExplanationModalProps {
  eventType: string
  onClose: () => void
}

export function EventExplanationModal({ eventType, onClose }: EventExplanationModalProps) {
  const ex = getEventExplanation(eventType)

  if (!ex) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
        <div
          className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6 max-w-md w-full shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="text-sm text-[var(--text-muted)]">No hay explicación para este evento.</p>
          <button
            type="button"
            onClick={onClose}
            className="mt-4 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm text-white"
          >
            Cerrar
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6 max-w-lg w-full shadow-xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-semibold text-[var(--accent)]">{ex.title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-white/10 text-[var(--text-muted)]"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-sm text-[var(--text)]">{ex.description}</p>
        <div>
          <p className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide mb-1">Lógica</p>
          <p className="text-sm text-[var(--text-muted)]">{ex.logic}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="w-full rounded-lg bg-[var(--accent)] py-2 text-sm font-medium text-white"
        >
          Cerrar
        </button>
      </div>
    </div>
  )
}
