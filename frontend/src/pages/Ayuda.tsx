import { useState } from 'react'
import { STRATEGY_EXPLANATIONS } from '../constants/strategyExplanations'
import { EVENT_EXPLANATIONS } from '../constants/eventExplanations'
import { HelpCircle, ChevronDown, ChevronUp, BookOpen, Zap } from 'lucide-react'

export function Ayuda() {
  const [showStrategies, setShowStrategies] = useState(true)
  const [showEvents, setShowEvents] = useState(false)

  return (
    <div className="space-y-8 max-w-3xl">
      <div className="flex items-center gap-2">
        <HelpCircle className="h-6 w-6 text-[var(--accent)]" />
        <h2 className="text-xl font-semibold">Cómo funciona el bot</h2>
      </div>
      <p className="text-sm text-[var(--text-muted)]">
        Aquí puedes ver de forma sencilla qué hace cada estrategia y qué significa cada evento del log.
      </p>

      {/* Estrategias */}
      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] overflow-hidden">
        <button
          type="button"
          className="flex w-full items-center justify-between p-4 text-left hover:bg-white/5"
          onClick={() => setShowStrategies((s) => !s)}
        >
          <span className="flex items-center gap-2 font-semibold text-[var(--text)]">
            <BookOpen className="h-5 w-5 text-[var(--accent)]" />
            Las 3 estrategias automáticas
          </span>
          {showStrategies ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </button>
        {showStrategies && (
          <div className="border-t border-white/10 p-4 space-y-6">
            {STRATEGY_EXPLANATIONS.map((s) => (
              <div key={s.id} className="rounded-lg border border-white/5 bg-[var(--surface)] p-4 space-y-2">
                <p className="font-medium text-[var(--accent)]">
                  {s.family} / {s.name} ({s.version})
                </p>
                <p className="text-sm font-medium text-[var(--text)]">{s.title}</p>
                <p className="text-sm text-[var(--text-muted)]">{s.short}</p>
                <div>
                  <p className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide mb-1">
                    Cómo funciona
                  </p>
                  <p className="text-sm text-[var(--text-muted)]">{s.howItWorks}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Eventos del log */}
      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] overflow-hidden">
        <button
          type="button"
          className="flex w-full items-center justify-between p-4 text-left hover:bg-white/5"
          onClick={() => setShowEvents((s) => !s)}
        >
          <span className="flex items-center gap-2 font-semibold text-[var(--text)]">
            <Zap className="h-5 w-5 text-[var(--accent)]" />
            Eventos del log del bot
          </span>
          {showEvents ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </button>
        {showEvents && (
          <div className="border-t border-white/10 p-4 space-y-3 max-h-[60vh] overflow-y-auto">
            {Object.entries(EVENT_EXPLANATIONS).map(([eventType, ex]) => (
              <div
                key={eventType}
                className="rounded-lg border border-white/5 bg-[var(--surface)] p-3 space-y-1"
              >
                <p className="font-mono text-xs font-medium text-[var(--accent)]">{eventType}</p>
                <p className="text-sm font-medium text-[var(--text)]">{ex.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{ex.description}</p>
                <p className="text-xs text-[var(--text-muted)] pt-1 border-t border-white/5">{ex.logic}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
