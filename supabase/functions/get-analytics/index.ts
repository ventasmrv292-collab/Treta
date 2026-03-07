import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

function round2(n: number) {
  return Math.round(n * 100) / 100;
}

function mapRpcToFrontend(rpc: {
  by_strategy?: Array<{
    strategy_family: string;
    strategy_name: string;
    total_trades: number;
    total_net_pnl: number;
    avg_net_pnl: number;
    total_gross_pnl: number;
    total_fees: number;
    win_rate: number;
    profit_factor: number;
    avg_win: number;
    avg_loss: number;
  }>;
  by_leverage?: Array<{
    leverage: number;
    total_trades: number;
    total_net_pnl: number;
    avg_net_pnl: number;
    total_fees: number;
    win_rate: number;
  }>;
  equity_curve?: Array<{ closed_at: string | null; cumulative_net_pnl: number }>;
}) {
  const byStrategy = (rpc.by_strategy ?? []).map((s) => {
    const winPct = (s.win_rate ?? 0) / 100;
    const expectancy = s.total_trades
      ? (s.avg_win ?? 0) * winPct + (s.avg_loss ?? 0) * (1 - winPct)
      : 0;
    return {
      strategy_name: s.strategy_name,
      strategy_family: s.strategy_family,
      total_trades: s.total_trades,
      net_pnl: String(round2(s.total_net_pnl ?? 0)),
      gross_pnl: String(round2(s.total_gross_pnl ?? 0)),
      total_fees: String(round2(s.total_fees ?? 0)),
      win_rate: round2(s.win_rate ?? 0),
      profit_factor: round2(s.profit_factor ?? 0),
      avg_win: String(round2(s.avg_win ?? 0)),
      avg_loss: String(round2(s.avg_loss ?? 0)),
      expectancy: String(round2(expectancy)),
    };
  });
  const byLeverage = (rpc.by_leverage ?? []).map((l) => ({
    leverage: l.leverage,
    total_trades: l.total_trades,
    net_pnl: String(round2(l.total_net_pnl ?? 0)),
    win_rate: round2(l.win_rate ?? 0),
    total_fees: String(round2(l.total_fees ?? 0)),
  }));
  const points = (rpc.equity_curve ?? []).map((p) => ({
    time: p.closed_at ? new Date(p.closed_at).toISOString() : null,
    equity: round2(p.cumulative_net_pnl ?? 0),
  }));
  return { byStrategy, byLeverage, equityCurve: { points } };
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  try {
    const { data: rpcData, error: rpcErr } = await supabase.rpc("get_analytics");

    if (!rpcErr && rpcData != null && typeof rpcData === "object") {
      const payload = rpcData as {
        by_strategy?: unknown[];
        by_leverage?: unknown[];
        equity_curve?: Array<{ closed_at: string | null; cumulative_net_pnl: number }>;
      };
      const { byStrategy, byLeverage, equityCurve } = mapRpcToFrontend({
        by_strategy: payload.by_strategy as Parameters<typeof mapRpcToFrontend>[0]["by_strategy"],
        by_leverage: payload.by_leverage as Parameters<typeof mapRpcToFrontend>[0]["by_leverage"],
        equity_curve: payload.equity_curve,
      });
      return new Response(
        JSON.stringify({ byStrategy, byLeverage, equityCurve }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    // Fallback: compute from trades (si la migración get_analytics no está aplicada)
    const { data: trades, error: tradesErr } = await supabase
      .from("trades")
      .select("id, strategy_name, strategy_family, leverage, closed_at, net_pnl_usdt, gross_pnl_usdt, entry_fee, exit_fee")
      .not("closed_at", "is", null)
      .not("net_pnl_usdt", "is", null)
      .order("closed_at", { ascending: true });

    if (tradesErr) {
      return new Response(
        JSON.stringify({ error: tradesErr.message }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
      );
    }

    const list = (trades ?? []) as {
      id: number;
      strategy_name: string;
      strategy_family: string;
      leverage: number;
      closed_at: string;
      net_pnl_usdt: number;
      gross_pnl_usdt: number;
      entry_fee: number;
      exit_fee: number;
    }[];

    const byStrategyMap = new Map<
      string,
      { strategy_name: string; strategy_family: string; total_trades: number; net_pnl: number; gross_pnl: number; fees: number; wins: number; losses: number; wins_sum: number; losses_sum: number; avg_win_sum: number; avg_loss_sum: number }
    >();
    const byLeverageMap = new Map<
      number,
      { leverage: number; total_trades: number; net_pnl: number; fees: number; wins: number }
    >();

    for (const t of list) {
      const netPnl = Number(t.net_pnl_usdt ?? 0);
      const grossPnl = Number(t.gross_pnl_usdt ?? 0);
      const fees = Number(t.entry_fee ?? 0) + Number(t.exit_fee ?? 0);
      const key = `${t.strategy_family}|${t.strategy_name}`;
      const existing = byStrategyMap.get(key);
      if (existing) {
        existing.total_trades += 1;
        existing.net_pnl += netPnl;
        existing.gross_pnl += grossPnl;
        existing.fees += fees;
        if (netPnl > 0) {
          existing.wins += 1;
          existing.wins_sum += netPnl;
          existing.avg_win_sum += netPnl;
        } else {
          existing.losses += 1;
          existing.losses_sum += netPnl;
          existing.avg_loss_sum += netPnl;
        }
      } else {
        byStrategyMap.set(key, {
          strategy_name: t.strategy_name,
          strategy_family: t.strategy_family,
          total_trades: 1,
          net_pnl: netPnl,
          gross_pnl: grossPnl,
          fees,
          wins: netPnl > 0 ? 1 : 0,
          losses: netPnl <= 0 ? 1 : 0,
          wins_sum: netPnl > 0 ? netPnl : 0,
          losses_sum: netPnl <= 0 ? netPnl : 0,
          avg_win_sum: netPnl > 0 ? netPnl : 0,
          avg_loss_sum: netPnl <= 0 ? netPnl : 0,
        });
      }

      const lev = Number(t.leverage);
      const levExisting = byLeverageMap.get(lev);
      if (levExisting) {
        levExisting.total_trades += 1;
        levExisting.net_pnl += netPnl;
        levExisting.fees += fees;
        if (netPnl > 0) levExisting.wins += 1;
      } else {
        byLeverageMap.set(lev, {
          leverage: lev,
          total_trades: 1,
          net_pnl: netPnl,
          fees,
          wins: netPnl > 0 ? 1 : 0,
        });
      }
    }

    const byStrategy = Array.from(byStrategyMap.values()).map((s) => {
      const total = s.total_trades;
      const winRate = total ? (s.wins / total) * 100 : 0;
      const lossesAbs = Math.abs(s.losses_sum);
      const profitFactor = lossesAbs ? s.wins_sum / lossesAbs : 0;
      const avgWin = s.wins ? s.avg_win_sum / s.wins : 0;
      const avgLoss = s.losses ? s.avg_loss_sum / s.losses : 0;
      const expectancy = total ? (avgWin * (s.wins / total) + avgLoss * (s.losses / total)) : 0;
      return {
        strategy_name: s.strategy_name,
        strategy_family: s.strategy_family,
        total_trades: s.total_trades,
        net_pnl: String(round2(s.net_pnl)),
        gross_pnl: String(round2(s.gross_pnl)),
        total_fees: String(round2(s.fees)),
        win_rate: round2(winRate),
        profit_factor: round2(profitFactor),
        avg_win: String(round2(avgWin)),
        avg_loss: String(round2(avgLoss)),
        expectancy: String(round2(expectancy)),
      };
    });

    const byLeverage = Array.from(byLeverageMap.values()).map((l) => {
      const total = l.total_trades;
      const winRate = total ? (l.wins / total) * 100 : 0;
      return {
        leverage: l.leverage,
        total_trades: l.total_trades,
        net_pnl: String(round2(l.net_pnl)),
        win_rate: round2(winRate),
        total_fees: String(round2(l.fees)),
      };
    });

    let cum = 0;
    const points = list.map((t) => {
      cum += Number(t.net_pnl_usdt ?? 0);
      return {
        time: t.closed_at ? new Date(t.closed_at).toISOString() : null,
        equity: round2(cum),
      };
    });

    return new Response(
      JSON.stringify({
        byStrategy,
        byLeverage,
        equityCurve: { points },
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String(e) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    );
  }
});
