import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";
import {
  getFeeRate,
  calcExitFee,
  computeFeesAndPnl,
  type MakerTaker,
  type PositionSide,
  type FeeConfigRow,
} from "../_shared/trading.ts";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

interface CloseTradeBody {
  trade_id: number;
  exit_price: number;
  exit_order_type?: string;
  maker_taker_exit?: string;
  exit_reason: string;
  closed_at?: string;
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST" && req.method !== "PATCH") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }

  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  try {
    const body = (await req.json()) as CloseTradeBody;
    const tradeId = Number(body.trade_id);
    if (!body.trade_id || isNaN(tradeId)) {
      return new Response(
        JSON.stringify({ error: "trade_id es requerido en el body" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }
    const { exit_price, exit_reason } = body;
    if (exit_price == null || exit_price <= 0 || !exit_reason) {
      return new Response(
        JSON.stringify({ error: "exit_price y exit_reason son requeridos" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    const { data: trade, error: tradeErr } = await supabase
      .from("trades")
      .select("*")
      .eq("id", tradeId)
      .single();
    if (tradeErr || !trade) {
      return new Response(
        JSON.stringify({ error: "Trade no encontrado" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 404 }
      );
    }

    if (trade.status !== "OPEN" || trade.closed_at) {
      return new Response(
        JSON.stringify({ error: "El trade no está abierto o ya fue cerrado" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    let feeConfig: FeeConfigRow;
    if (trade.fee_config_id) {
      const { data: fc, error: fcErr } = await supabase
        .from("fee_configs")
        .select("maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding")
        .eq("id", trade.fee_config_id)
        .single();
      if (fcErr || !fc) {
        return new Response(
          JSON.stringify({ error: "Fee config del trade no encontrado" }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
        );
      }
      feeConfig = fc as FeeConfigRow;
    } else {
      const { data: fc } = await supabase
        .from("fee_configs")
        .select("maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding")
        .eq("is_default", true)
        .limit(1)
        .single();
      feeConfig = (fc ?? {
        maker_fee_bps: 2,
        taker_fee_bps: 4,
        bnb_discount_pct: 10,
        default_slippage_bps: 5,
        include_funding: true,
      }) as FeeConfigRow;
    }

    const quantity = Number(trade.quantity);
    const entryPrice = Number(trade.entry_price);
    const exitPrice = Number(exit_price);
    const positionSide = (trade.position_side || "LONG") as PositionSide;
    const makerTakerEntry = (trade.maker_taker_entry || "TAKER") as MakerTaker;
    const makerTakerExit = (body.maker_taker_exit || "TAKER").toUpperCase() as MakerTaker;

    const result = computeFeesAndPnl(
      quantity,
      entryPrice,
      exitPrice,
      positionSide,
      makerTakerEntry,
      makerTakerExit,
      feeConfig,
      undefined,
      0
    );

    const closedAt = body.closed_at ? new Date(body.closed_at).toISOString() : new Date().toISOString();
    const marginUsed = Number(trade.margin_used_usdt);

    const { data: updatedTrade, error: updateErr } = await supabase
      .from("trades")
      .update({
        exit_price: exitPrice,
        exit_order_type: body.exit_order_type ?? "MARKET",
        maker_taker_exit: makerTakerExit,
        exit_reason: body.exit_reason,
        closed_at: closedAt,
        entry_notional: result.entryNotional,
        exit_notional: result.exitNotional,
        entry_fee: result.entryFee,
        exit_fee: result.exitFee,
        funding_fee: 0,
        slippage_usdt: result.slippageUsdt,
        gross_pnl_usdt: result.grossPnlUsdt,
        net_pnl_usdt: result.netPnlUsdt,
        pnl_pct_notional: result.entryNotional
          ? Math.round((result.netPnlUsdt / result.entryNotional) * 10000) / 100
          : null,
        pnl_pct_margin: marginUsed
          ? Math.round((result.netPnlUsdt / marginUsed) * 10000) / 100
          : null,
        status: "CLOSED",
        updated_at: closedAt,
      })
      .eq("id", tradeId)
      .select()
      .single();
    if (updateErr) {
      return new Response(
        JSON.stringify({ error: "Error al cerrar trade: " + updateErr.message }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
      );
    }

    if (trade.account_id) {
      const { data: account } = await supabase
        .from("paper_accounts")
        .select("*")
        .eq("id", trade.account_id)
        .single();
      if (account) {
        const newUsedMargin = Math.max(0, Number(account.used_margin_usdt) - marginUsed);
        const totalFeesTrade = result.entryFee + result.exitFee;
        const newCurrentBalance = Number(account.current_balance_usdt) + result.netPnlUsdt;
        const newRealizedPnl = Number(account.realized_pnl_usdt) + result.netPnlUsdt;
        const newTotalFees = Number(account.total_fees_usdt) + totalFeesTrade;
        const newAvailable = newCurrentBalance - newUsedMargin;

        await supabase
          .from("paper_accounts")
          .update({
            used_margin_usdt: newUsedMargin,
            current_balance_usdt: newCurrentBalance,
            realized_pnl_usdt: newRealizedPnl,
            total_fees_usdt: newTotalFees,
            unrealized_pnl_usdt: 0,
            available_balance_usdt: newAvailable,
            updated_at: closedAt,
          })
          .eq("id", trade.account_id);

        const balanceBefore = Number(account.current_balance_usdt);
        const balanceAfter = newCurrentBalance;
        await supabase.from("account_ledger").insert({
          account_id: trade.account_id,
          trade_id: tradeId,
          backtest_run_id: null,
          event_type: "TRADE_CLOSE",
          amount_usdt: result.netPnlUsdt,
          balance_before_usdt: balanceBefore,
          balance_after_usdt: balanceAfter,
          meta_json: JSON.stringify({
            exit_reason: body.exit_reason,
            net_pnl_usdt: result.netPnlUsdt,
            exit_fee: result.exitFee,
          }),
        });

        await supabase
          .from("trades")
          .update({ capital_after_usdt: newCurrentBalance })
          .eq("id", tradeId);
      }
    }

    return new Response(JSON.stringify(updatedTrade), {
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
