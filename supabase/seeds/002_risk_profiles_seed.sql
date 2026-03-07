-- Risk profiles iniciales
INSERT INTO public.risk_profiles (name, sizing_mode, fixed_quantity, fixed_notional_usdt, risk_pct_per_trade, max_open_positions, max_margin_pct_of_account, max_daily_loss_usdt, max_daily_loss_pct, cooldown_after_losses, allowed_leverage_json)
SELECT 'Conservador', 'RISK_PCT_OF_EQUITY', NULL, NULL, 0.5, 3, 30, 50, 5, 2, '[10]'
WHERE NOT EXISTS (SELECT 1 FROM public.risk_profiles WHERE name = 'Conservador');
INSERT INTO public.risk_profiles (name, sizing_mode, fixed_quantity, fixed_notional_usdt, risk_pct_per_trade, max_open_positions, max_margin_pct_of_account, max_daily_loss_usdt, max_daily_loss_pct, cooldown_after_losses, allowed_leverage_json)
SELECT 'Moderado', 'FIXED_NOTIONAL', NULL, 200, NULL, 5, 50, 100, 10, 3, '[10, 20]'
WHERE NOT EXISTS (SELECT 1 FROM public.risk_profiles WHERE name = 'Moderado');
INSERT INTO public.risk_profiles (name, sizing_mode, fixed_quantity, fixed_notional_usdt, risk_pct_per_trade, max_open_positions, max_margin_pct_of_account, max_daily_loss_usdt, max_daily_loss_pct, cooldown_after_losses, allowed_leverage_json)
SELECT 'Fijo x contrato', 'FIXED_QTY', 0.001, NULL, NULL, 5, 80, NULL, 15, NULL, '[10, 20]'
WHERE NOT EXISTS (SELECT 1 FROM public.risk_profiles WHERE name = 'Fijo x contrato');
