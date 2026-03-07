import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }

  const url = new URL(req.url);
  const accountIdParam = url.searchParams.get("account_id");
  const accountId = accountIdParam ? parseInt(accountIdParam, 10) : null;

  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  try {
    const closed = "closed_at.not.is.null";
    const hasPnl = "net_pnl_usdt.not.is.null";

    const { data: closedTrades } = await supabase
      .from("trades")
      .select("id, net_pnl_usdt, gross_pnl_usdt, entry_fee, exit_fee, funding_fee, strategy_name, strategy_family, leverage")
      .not("closed_at", "is", null)
      .not("net_pnl_usdt", "is", null);

    const trades = closedTrades ?? [];
    const totalTrades = trades.length;
    const winners = trades.filter((t) => Number(t.net_pnl_usdt) > 0);
    const winningTrades = winners.length;
    const winRate = totalTrades ? Math.round((winningTrades / totalTrades) * 10000) / 100 : 0;

    let netPnl = 0;
    let grossPnl = 0;
    let totalFees = 0;
    for (const t of trades) {
      netPnl += Number(t.net_pnl_usdt ?? 0);
      grossPnl += Number(t.gross_pnl_usdt ?? 0);
      totalFees += Number(t.entry_fee ?? 0) + Number(t.exit_fee ?? 0) + Number(t.funding_fee ?? 0);
    }

    const winsSum = winners.reduce((s, t) => s + Number(t.net_pnl_usdt), 0);
    const lossesSum = trades.filter((t) => Number(t.net_pnl_usdt) < 0).reduce((s, t) => s + Number(t.net_pnl_usdt), 0);
    const lossesAbs = Math.abs(lossesSum);
    const profitFactor = lossesAbs ? Math.round((winsSum / lossesAbs) * 10000) / 10000 : (winsSum ? 999 : 0);

    const pnlByStrategy: Record<string, number> = {};
    for (const t of trades) {
      const key = `${t.strategy_family}|${t.strategy_name}`;
      pnlByStrategy[key] = (pnlByStrategy[key] ?? 0) + Number(t.net_pnl_usdt ?? 0);
    }
    const pnl_by_strategy = Object.entries(pnlByStrategy).map(([k, v]) => {
      const [strategy_family, strategy_name] = k.split("|");
      return { strategy_family, strategy_name, net_pnl: Math.round(v * 10000) / 10000 };
    });

    const pnlByLeverage: Record<number, number> = {};
    for (const t of trades) {
      const lev = Number(t.leverage);
      pnlByLeverage[lev] = (pnlByLeverage[lev] ?? 0) + Number(t.net_pnl_usdt ?? 0);
    }
    const pnl_by_leverage = Object.entries(pnlByLeverage).map(([leverage, net_pnl]) => ({
      leverage: Number(leverage),
      net_pnl: Math.round(net_pnl * 10000) / 10000,
    }));

    let account: Record<string, unknown> | null = null;
    let equityUsdt: string | null = null;
    let openPositionsCount = 0;

    if (accountId) {
      const { data: acc } = await supabase.from("paper_accounts").select("*").eq("id", accountId).single();
      if (acc) {
        account = {
          id: acc.id,
          name: acc.name,
          base_currency: acc.base_currency,
          initial_balance_usdt: acc.initial_balance_usdt,
          current_balance_usdt: acc.current_balance_usdt,
          available_balance_usdt: acc.available_balance_usdt,
          used_margin_usdt: acc.used_margin_usdt,
          realized_pnl_usdt: acc.realized_pnl_usdt,
          unrealized_pnl_usdt: acc.unrealized_pnl_usdt,
          total_fees_usdt: acc.total_fees_usdt,
          status: acc.status,
        };
        equityUsdt = String(Number(acc.current_balance_usdt) + Number(acc.unrealized_pnl_usdt ?? 0));
      }
      const { count } = await supabase
        .from("trades")
        .select("id", { count: "exact", head: true })
        .eq("account_id", accountId)
        .is("closed_at", null);
      openPositionsCount = count ?? 0;
    }

    const response = {
      btc_price: null as string | null,
      total_trades: totalTrades,
      win_rate: winRate,
      net_pnl: String(Math.round(netPnl * 10000) / 10000),
      gross_pnl: String(Math.round(grossPnl * 10000) / 10000),
      total_fees: String(Math.round(totalFees * 10000) / 10000),
      profit_factor: profitFactor,
      pnl_by_strategy,
      pnl_by_leverage,
      account,
      equity_usdt: equityUsdt,
      open_positions_count: openPositionsCount,
    };

    return new Response(JSON.stringify(response), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 200,
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String(e) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    );
  }
});
