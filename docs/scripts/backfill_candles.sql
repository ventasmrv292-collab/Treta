-- ============================================================
-- Backfill: limpiar datos de candles antes de reinyectar desde Binance
-- Ejecutar solo si quieres borrar todo (o por símbolo/intervalo) y volver a sincronizar.
-- La reingesta se hace desde el backend (scheduler o llamada manual al sync).
-- ============================================================

-- OPCIÓN A: Borrar solo un símbolo e intervalo (ej. BTCUSDT 1m)
-- DELETE FROM public.candles WHERE symbol = 'BTCUSDT' AND interval = '1m';

-- OPCIÓN B: Borrar todos los datos de candles (tabla vacía para reingesta completa)
-- TRUNCATE TABLE public.candles RESTART IDENTITY;

-- OPCIÓN C: Borrar solo filas con volume = 0 o marcadas como inválidas (si tienes validation_status)
-- DELETE FROM public.candles WHERE volume = 0;
-- DELETE FROM public.candles WHERE validation_status = 'INVALID';

-- Descomenta la línea que quieras ejecutar y ejecuta en Supabase SQL Editor.
-- Después, arranca el backend para que el scheduler rellene con sync_candles_to_db (Binance),
-- o invoca manualmente el job de sync (según tu implementación).
