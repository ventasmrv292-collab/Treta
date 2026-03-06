-- ============================================================
-- Migración 004: RLS en tablas nuevas y existentes
-- Ajustar políticas según tu auth (ej. anon/authenticated por proyecto).
-- ============================================================

ALTER TABLE public.paper_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.account_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.signal_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_equity_curve ENABLE ROW LEVEL SECURITY;

-- Políticas por defecto: permitir todo a authenticated y anon (para API server-side).
-- En producción restringir por user_id si añades columna user_id a paper_accounts.
CREATE POLICY "Allow read paper_accounts" ON public.paper_accounts FOR SELECT USING (true);
CREATE POLICY "Allow insert paper_accounts" ON public.paper_accounts FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update paper_accounts" ON public.paper_accounts FOR UPDATE USING (true);

CREATE POLICY "Allow read account_ledger" ON public.account_ledger FOR SELECT USING (true);
CREATE POLICY "Allow insert account_ledger" ON public.account_ledger FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow read signal_events" ON public.signal_events FOR SELECT USING (true);
CREATE POLICY "Allow insert signal_events" ON public.signal_events FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update signal_events" ON public.signal_events FOR UPDATE USING (true);

CREATE POLICY "Allow read backtest_equity_curve" ON public.backtest_equity_curve FOR SELECT USING (true);
CREATE POLICY "Allow insert backtest_equity_curve" ON public.backtest_equity_curve FOR INSERT WITH CHECK (true);

-- Opcional: habilitar RLS en tablas existentes si aún no está
-- ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE public.strategies ENABLE ROW LEVEL SECURITY;
-- etc.
