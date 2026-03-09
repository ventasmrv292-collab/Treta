import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'
import esMessages from '../locales/es.json'
import ptPTMessages from '../locales/pt-PT.json'

const STORAGE_KEY = 'app-locale'
export type Locale = 'es' | 'pt-PT'

type Messages = Record<string, unknown>

function getNested(obj: Messages, path: string): string | undefined {
  const parts = path.split('.')
  let current: unknown = obj
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined
    current = (current as Record<string, unknown>)[part]
  }
  return typeof current === 'string' ? current : undefined
}

function interpolate(str: string, vars: Record<string, string | number>): string {
  return str.replace(/\{\{(\w+)\}\}/g, (_, key) => String(vars[key] ?? `{{${key}}}`))
}

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: string, vars?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

const messages: Record<Locale, Messages> = { es: esMessages as Messages, 'pt-PT': ptPTMessages as Messages }

function getStoredLocale(): Locale {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    if (s === 'es' || s === 'pt-PT') return s
  } catch {}
  return 'es'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getStoredLocale)

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {}
  }, [])

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      const msg = getNested(messages[locale], key) ?? getNested(messages.es, key) ?? key
      return vars ? interpolate(msg, vars) : msg
    },
    [locale]
  )

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}
