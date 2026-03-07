-- ============================================================
-- Seed inicial: fee config, estrategias (1.0.0), paper account 1000 USDT
-- Ejecutar después de las migraciones.
-- ============================================================

-- 1) Fee config por defecto
INSERT INTO public.fee_configs (name, maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding, is_default)
SELECT 'Binance Realista', 2.0, 4.0, 10.0, 5.0, true, true
WHERE NOT EXISTS (SELECT 1 FROM public.fee_configs WHERE is_default = true);

-- 2) Estrategias: BREAKOUT/breakout_volume_v1/1.0.0, MEAN_REVERSION/vwap_snapback_v1/1.0.0, TREND_PULLBACK/ema_pullback_v1/1.0.0
INSERT INTO public.strategies (family, name, version, description, default_params_json, active)
VALUES
    ('BREAKOUT', 'breakout_volume_v1', '1.0.0', 'Breakout por volumen', '{}', true),
    ('MEAN_REVERSION', 'vwap_snapback_v1', '1.0.0', 'Mean reversion VWAP snapback', '{}', true),
    ('TREND_PULLBACK', 'ema_pullback_v1', '1.0.0', 'Pullback a EMA en tendencia', '{}', true)
ON CONFLICT (family, name, version) DO NOTHING;

-- 3) Paper account por defecto (1000 USDT)
INSERT INTO public.paper_accounts (name, base_currency, initial_balance_usdt, current_balance_usdt, available_balance_usdt, used_margin_usdt, realized_pnl_usdt, unrealized_pnl_usdt, total_fees_usdt, status)
SELECT 'Main Paper Account', 'USDT', 1000.0000, 1000.0000, 1000.0000, 0.0000, 0.0000, 0.0000, 0.0000, 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM public.paper_accounts WHERE name = 'Main Paper Account' LIMIT 1);
