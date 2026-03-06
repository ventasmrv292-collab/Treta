/**
 * Base URL del backend API.
 * En local: vacío → se usa el proxy de Vite a localhost:8000.
 * En producción (Vercel): definir VITE_API_BASE_URL en el proyecto de Vercel
 * apuntando a tu backend (ej: https://tu-backend.render.com o https://tu-backend.fly.dev).
 */
export const API_BASE =
  typeof import.meta.env.VITE_API_BASE_URL === 'string' && import.meta.env.VITE_API_BASE_URL.trim() !== ''
    ? import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')
    : ''

/** URL base para WebSocket (precio en tiempo real). */
export const WS_BASE = API_BASE
  ? (API_BASE.startsWith('https') ? API_BASE.replace(/^https/, 'wss') : API_BASE.replace(/^http/, 'ws'))
  : 'ws://localhost:8000'
