-- ============================================================
-- Migración 04: RLS en tablas
-- ============================================================

ALTER TABLE public.paper_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.account_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.signal_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_equity_curve ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fee_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_results ENABLE ROW LEVEL SECURITY;

-- Políticas: permitir todo para servicio (anon/authenticated). Ajustar en producción por user_id.
DROP POLICY IF EXISTS "Allow read paper_accounts" ON public.paper_accounts;
DROP POLICY IF EXISTS "Allow insert paper_accounts" ON public.paper_accounts;
DROP POLICY IF EXISTS "Allow update paper_accounts" ON public.paper_accounts;
CREATE POLICY "Allow read paper_accounts" ON public.paper_accounts FOR SELECT USING (true);
CREATE POLICY "Allow insert paper_accounts" ON public.paper_accounts FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update paper_accounts" ON public.paper_accounts FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Allow read account_ledger" ON public.account_ledger;
DROP POLICY IF EXISTS "Allow insert account_ledger" ON public.account_ledger;
CREATE POLICY "Allow read account_ledger" ON public.account_ledger FOR SELECT USING (true);
CREATE POLICY "Allow insert account_ledger" ON public.account_ledger FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Allow read signal_events" ON public.signal_events;
DROP POLICY IF EXISTS "Allow insert signal_events" ON public.signal_events;
DROP POLICY IF EXISTS "Allow update signal_events" ON public.signal_events;
CREATE POLICY "Allow read signal_events" ON public.signal_events FOR SELECT USING (true);
CREATE POLICY "Allow insert signal_events" ON public.signal_events FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update signal_events" ON public.signal_events FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Allow read backtest_equity_curve" ON public.backtest_equity_curve;
DROP POLICY IF EXISTS "Allow insert backtest_equity_curve" ON public.backtest_equity_curve;
CREATE POLICY "Allow read backtest_equity_curve" ON public.backtest_equity_curve FOR SELECT USING (true);
CREATE POLICY "Allow insert backtest_equity_curve" ON public.backtest_equity_curve FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all trades" ON public.trades;
CREATE POLICY "Allow all trades" ON public.trades FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all strategies" ON public.strategies;
CREATE POLICY "Allow all strategies" ON public.strategies FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all fee_configs" ON public.fee_configs;
CREATE POLICY "Allow all fee_configs" ON public.fee_configs FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all candles" ON public.candles;
CREATE POLICY "Allow all candles" ON public.candles FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all backtest_runs" ON public.backtest_runs;
CREATE POLICY "Allow all backtest_runs" ON public.backtest_runs FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all backtest_results" ON public.backtest_results;
CREATE POLICY "Allow all backtest_results" ON public.backtest_results FOR ALL USING (true) WITH CHECK (true);
