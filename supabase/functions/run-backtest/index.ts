import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";
import {
  computeFeesAndPnl,
  type FeeConfigRow,
  type PositionSide,
} from "../_shared/trading.ts";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

interface RunBacktestBody {
  strategy_family: string;
  strategy_name: string;
  strategy_version: string;
  symbol?: string;
  interval?: string;
  start_time: string;
  end_time: string;
  initial_capital: number | string;
  leverage?: number;
  fee_profile?: string;
  slippage_bps?: number;
  params_json?: string | null;
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  try {
    const body = (await req.json()) as RunBacktestBody;
    const {
      strategy_family,
      strategy_name,
      strategy_version,
      start_time,
      end_time,
      initial_capital,
    } = body;
    if (!strategy_family || !strategy_name || !strategy_version || !start_time || !end_time) {
      return new Response(
        JSON.stringify({ error: "Faltan campos: strategy_family, strategy_name, strategy_version, start_time, end_time" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    const symbol = body.symbol ?? "BTCUSDT";
    const interval = body.interval ?? "15m";
    const leverage = Math.max(1, Math.min(125, Number(body.leverage) || 10));
    const initialCapital = Math.max(0, Number(initial_capital) || 1000);
    const slippageBps = Number(body.slippage_bps) || 5;

    const { data: feeConfigRow } = await supabase
      .from("fee_configs")
      .select("id, maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding")
      .eq("is_default", true)
      .limit(1)
      .single();
    const feeConfig: FeeConfigRow = feeConfigRow
      ? {
          maker_fee_bps: Number(feeConfigRow.maker_fee_bps),
          taker_fee_bps: Number(feeConfigRow.taker_fee_bps),
          bnb_discount_pct: Number(feeConfigRow.bnb_discount_pct),
          default_slippage_bps: Number(feeConfigRow.default_slippage_bps ?? slippageBps),
          include_funding: Boolean(feeConfigRow.include_funding),
        }
      : {
          maker_fee_bps: 2,
          taker_fee_bps: 4,
          bnb_discount_pct: 10,
          default_slippage_bps: slippageBps,
          include_funding: true,
        };

    const feeConfigId = (feeConfigRow as { id?: number })?.id ?? null;
    const strategyId = null;

    const { data: run, error: runErr } = await supabase
      .from("backtest_runs")
      .insert({
        strategy_family,
        strategy_name,
        strategy_version,
        strategy_id: strategyId,
        symbol,
        interval,
        start_time: start_time,
        end_time: end_time,
        initial_capital: initialCapital,
        leverage,
        fee_profile: body.fee_profile ?? "realistic",
        slippage_bps: slippageBps,
        params_json: body.params_json ?? null,
        fee_config_id: feeConfigId,
        status: "running",
      })
      .select()
      .single();
    if (runErr) {
      return new Response(
        JSON.stringify({ error: "Error al crear backtest_run: " + runErr.message }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
      );
    }

    const startDate = new Date(start_time);
    const endDate = new Date(end_time);

    const { data: candlesRows, error: candlesErr } = await supabase
      .from("candles")
      .select("open_time, open, high, low, close, volume")
      .eq("symbol", symbol)
      .eq("interval", interval)
      .gte("open_time", startDate.toISOString())
      .lte("open_time", endDate.toISOString())
      .order("open_time", { ascending: true });

    if (candlesErr || !candlesRows?.length) {
      await supabase
        .from("backtest_runs")
        .update({
          status: "completed",
          total_trades: 0,
          net_pnl: 0,
          gross_pnl: 0,
          total_fees: 0,
          win_rate: 0,
          profit_factor: 0,
          max_drawdown_pct: 0,
          final_capital: initialCapital,
          peak_equity: initialCapital,
          min_equity: initialCapital,
          total_funding: 0,
          total_slippage: 0,
          used_margin_peak: 0,
        })
        .eq("id", run.id);
      const { data: completed } = await supabase.from("backtest_runs").select("*").eq("id", run.id).single();
      return new Response(JSON.stringify(completed), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 200,
      });
    }

    const candles = candlesRows as { open_time: string; open: number; high: number; low: number; close: number; volume: number }[];
    if (candles.length < 2) {
      await supabase
        .from("backtest_runs")
        .update({
          status: "completed",
          total_trades: 0,
          net_pnl: 0,
          gross_pnl: 0,
          total_fees: 0,
          win_rate: 0,
          profit_factor: 0,
          max_drawdown_pct: 0,
          final_capital: initialCapital,
          peak_equity: initialCapital,
          min_equity: initialCapital,
          total_funding: 0,
          total_slippage: 0,
          used_margin_peak: 0,
        })
        .eq("id", run.id);
      const { data: completed } = await supabase.from("backtest_runs").select("*").eq("id", run.id).single();
      return new Response(JSON.stringify(completed), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 200,
      });
    }

    const first = candles[0];
    const last = candles[candles.length - 1];
    const entryPrice = first.open;
    const exitPrice = last.close;
    const entryTime = first.open_time;
    const exitTime = last.open_time;
    const qty = (initialCapital * leverage) / entryPrice;
    const qtyRounded = Math.round(qty * 1e8) / 1e8;

    const result = computeFeesAndPnl(
      qtyRounded,
      entryPrice,
      exitPrice,
      "LONG" as PositionSide,
      "TAKER",
      "TAKER",
      feeConfig,
      slippageBps,
      0
    );

    const totalFees = result.entryFee + result.exitFee;
    const totalSlippage = result.slippageUsdt;
    const totalFunding = 0;
    const finalCapital = initialCapital + result.netPnlUsdt;
    const peakEquity = Math.max(initialCapital, finalCapital);
    const minEquity = Math.min(initialCapital, finalCapital);
    const marginUsed = (qtyRounded * entryPrice) / leverage;
    const usedMarginPeak = marginUsed;

    await supabase.from("backtest_results").insert({
      run_id: run.id,
      trade_index: 0,
      entry_time: entryTime,
      exit_time: exitTime,
      position_side: "LONG",
      entry_price: entryPrice,
      exit_price: exitPrice,
      quantity: qtyRounded,
      gross_pnl: result.grossPnlUsdt,
      fees: totalFees,
      net_pnl: result.netPnlUsdt,
      exit_reason: "backtest_end",
    });

    const equityPoints = [
      { point_time: entryTime, equity_usdt: initialCapital, balance_usdt: initialCapital, used_margin_usdt: marginUsed, drawdown_pct: 0 },
      { point_time: exitTime, equity_usdt: finalCapital, balance_usdt: finalCapital, used_margin_usdt: 0, drawdown_pct: 0 },
    ];
    for (const p of equityPoints) {
      await supabase.from("backtest_equity_curve").insert({
        run_id: run.id,
        point_time: p.point_time,
        equity_usdt: p.equity_usdt,
        balance_usdt: p.balance_usdt,
        used_margin_usdt: p.used_margin_usdt,
        drawdown_pct: p.drawdown_pct,
      });
    }

    const winRate = result.netPnlUsdt > 0 ? 100 : 0;
    const profitFactor = totalFees > 0 ? Math.round((result.grossPnlUsdt / totalFees) * 10000) / 10000 : 0;

    await supabase
      .from("backtest_runs")
      .update({
        status: "completed",
        total_trades: 1,
        net_pnl: result.netPnlUsdt,
        gross_pnl: result.grossPnlUsdt,
        total_fees: totalFees,
        win_rate: winRate,
        profit_factor: profitFactor,
        max_drawdown_pct: 0,
        final_capital: finalCapital,
        peak_equity: peakEquity,
        min_equity: minEquity,
        total_funding: totalFunding,
        total_slippage: totalSlippage,
        used_margin_peak: usedMarginPeak,
      })
      .eq("id", run.id);

    const { data: completedRun } = await supabase.from("backtest_runs").select("*").eq("id", run.id).single();
    return new Response(JSON.stringify(completedRun), {
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
