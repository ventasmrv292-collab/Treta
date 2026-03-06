-- ============================================================
-- Seed inicial: una paper account, un fee config por defecto, 3 estrategias
-- Ejecutar después de las migraciones 001, 002, 003.
-- ============================================================

-- 1) Fee config por defecto (solo si no existe ninguno con is_default)
INSERT INTO public.fee_configs (name, maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding, is_default)
SELECT 'Binance Realista', 2.0, 4.0, 10.0, 5.0, true, true
WHERE NOT EXISTS (SELECT 1 FROM public.fee_configs WHERE is_default = true);

-- 2) Estrategias (ignorar si ya existen por unique constraint)
INSERT INTO public.strategies (family, name, version, description, default_params_json, active)
VALUES
    ('BREAKOUT', 'breakout_volume_v1', 'v1', 'Breakout por volumen', '{}', true),
    ('MEAN_REVERSION', 'vwap_snapback_v1', 'v1', 'Mean reversion VWAP snapback', '{}', true),
    ('TREND_PULLBACK', 'ema_pullback_v1', 'v1', 'Pullback a EMA en tendencia', '{}', true)
ON CONFLICT (family, name, version) DO NOTHING;

-- 3) Paper account por defecto
INSERT INTO public.paper_accounts (name, base_currency, initial_balance_usdt, current_balance_usdt, available_balance_usdt, used_margin_usdt, realized_pnl_usdt, unrealized_pnl_usdt, total_fees_usdt, status)
SELECT 'Main Paper Account', 'USDT', 1000.0000, 1000.0000, 1000.0000, 0.0000, 0.0000, 0.0000, 0.0000, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM public.paper_accounts WHERE name = 'Main Paper Account' LIMIT 1);
