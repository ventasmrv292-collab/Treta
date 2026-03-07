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

  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  try {
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
        net_pnl: String(Math.round(s.net_pnl * 100) / 100),
        gross_pnl: String(Math.round(s.gross_pnl * 100) / 100),
        total_fees: String(Math.round(s.fees * 100) / 100),
        win_rate: Math.round(winRate * 100) / 100,
        profit_factor: Math.round(profitFactor * 10000) / 10000,
        avg_win: String(Math.round(avgWin * 100) / 100),
        avg_loss: String(Math.round(avgLoss * 100) / 100),
        expectancy: String(Math.round(expectancy * 100) / 100),
      };
    });

    const byLeverage = Array.from(byLeverageMap.values()).map((l) => {
      const total = l.total_trades;
      const winRate = total ? (l.wins / total) * 100 : 0;
      return {
        leverage: l.leverage,
        total_trades: l.total_trades,
        net_pnl: String(Math.round(l.net_pnl * 100) / 100),
        win_rate: Math.round(winRate * 100) / 100,
        total_fees: String(Math.round(l.fees * 100) / 100),
      };
    });

    let cum = 0;
    const points = list.map((t) => {
      cum += Number(t.net_pnl_usdt ?? 0);
      return {
        time: t.closed_at ? new Date(t.closed_at).toISOString() : null,
        equity: Math.round(cum * 100) / 100,
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
