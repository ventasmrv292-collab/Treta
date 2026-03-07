/**
 * Base URL del backend API (FastAPI).
 * En local: vacío → se usa el proxy de Vite a localhost:8000.
 * En producción: definir VITE_API_BASE_URL apuntando a tu backend.
 */
export const API_BASE =
  typeof import.meta.env.VITE_API_BASE_URL === 'string' && import.meta.env.VITE_API_BASE_URL.trim() !== ''
    ? import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')
    : ''

/**
 * Supabase project URL (ej: https://xxx.supabase.co).
 * Si está definido junto con VITE_SUPABASE_ANON_KEY, el frontend usará Edge Functions
 * para crear/cerrar trades, dashboard y backtest.
 */
export const SUPABASE_URL =
  typeof import.meta.env.VITE_SUPABASE_URL === 'string' && import.meta.env.VITE_SUPABASE_URL.trim() !== ''
    ? import.meta.env.VITE_SUPABASE_URL.replace(/\/$/, '')
    : ''

/** Anon key de Supabase para invocar Edge Functions desde el navegador. */
export const SUPABASE_ANON_KEY =
  typeof import.meta.env.VITE_SUPABASE_ANON_KEY === 'string' && import.meta.env.VITE_SUPABASE_ANON_KEY.trim() !== ''
    ? import.meta.env.VITE_SUPABASE_ANON_KEY
    : ''

/** true si el frontend debe usar Supabase (Edge Functions + REST) para trades, dashboard y backtest. */
export const USE_SUPABASE = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY)

/** URL base para WebSocket (precio en tiempo real). */
export const WS_BASE = API_BASE
  ? (API_BASE.startsWith('https') ? API_BASE.replace(/^https/, 'wss') : API_BASE.replace(/^http/, 'ws'))
  : 'ws://localhost:8000'
