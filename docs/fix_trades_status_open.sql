-- ============================================================
-- Corregir trades cerrados que quedaron con status 'OPEN'
-- Ejecutar una vez en Supabase SQL Editor.
-- Marca como CLOSED los que tienen closed_at o net_pnl_usdt rellenado.
-- ============================================================

UPDATE public.trades
SET status = 'CLOSED'
WHERE status = 'OPEN'
  AND (closed_at IS NOT NULL OR net_pnl_usdt IS NOT NULL);
