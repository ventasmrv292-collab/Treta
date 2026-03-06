import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { clsx } from 'clsx'

type Toast = { id: number; message: string; type: 'success' | 'error' | 'info' }

const ToastContext = createContext<{
  toasts: Toast[]
  addToast: (message: string, type?: Toast['type']) => void
  removeToast: (id: number) => void
} | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) return { addToast: () => {}, removeToast: () => {}, toasts: [] }
  return ctx
}

export function Toaster({ children }: { children?: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)
  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    idRef.current += 1
    const nextId = idRef.current
    setToasts((t) => [...t, { id: nextId, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== nextId)), 4000)
  }, [])
  const removeToast = useCallback((toastId: number) => {
    setToasts((t) => t.filter((x) => x.id !== toastId))
  }, [])
  const value = useMemo(() => ({ toasts, addToast, removeToast }), [toasts, addToast, removeToast])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={clsx(
              'flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg',
              t.type === 'success' && 'border-green-500/50 bg-green-500/20 text-green-300',
              t.type === 'error' && 'border-red-500/50 bg-red-500/20 text-red-300',
              t.type === 'info' && 'border-[var(--accent)]/50 bg-[var(--accent)]/20'
            )}
          >
            <span>{t.message}</span>
            <button
              type="button"
              onClick={() => removeToast(t.id)}
              className="ml-2 rounded p-1 hover:bg-white/20"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
