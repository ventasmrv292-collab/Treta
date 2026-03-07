import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { corsHeaders } from "../_shared/cors.ts";
import {
  getFeeRate,
  calcEntryFee,
  calcMarginUsed,
  validateAvailableCapital,
  type MakerTaker,
  type FeeConfigRow,
} from "../_shared/trading.ts";

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

interface CreateTradeBody {
  source?: string;
  symbol: string;
  market?: string;
  strategy_family: string;
  strategy_name: string;
  strategy_version: string;
  timeframe: string;
  position_side: string;
  order_side_entry: string;
  order_type_entry?: string;
  maker_taker_entry?: string;
  leverage: number;
  quantity: number;
  entry_price: number;
  take_profit?: number | null;
  stop_loss?: number | null;
  notes?: string | null;
  account_id?: number | null;
  fee_config_id?: number | null;
  risk_profile_id?: number | null;
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
    const body = (await req.json()) as CreateTradeBody;
    const {
      symbol,
      strategy_family,
      strategy_name,
      strategy_version,
      timeframe,
      position_side,
      order_side_entry,
      leverage,
      quantity,
      entry_price,
    } = body;

    if (
      !symbol ||
      !strategy_family ||
      !strategy_name ||
      !strategy_version ||
      !timeframe ||
      !position_side ||
      !order_side_entry ||
      leverage == null ||
      leverage < 1 ||
      quantity == null ||
      quantity <= 0 ||
      entry_price == null ||
      entry_price <= 0
    ) {
      return new Response(
        JSON.stringify({ error: "Faltan campos requeridos o valores inválidos" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    let accountId = body.account_id ?? null;
    if (accountId == null) {
      const { data: accounts } = await supabase
        .from("paper_accounts")
        .select("id")
        .eq("status", "ACTIVE")
        .limit(1);
      if (accounts?.length) accountId = accounts[0].id;
    }
    if (accountId == null) {
      return new Response(
        JSON.stringify({ error: "No hay cuenta paper activa. Proporciona account_id o crea una cuenta." }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    const { data: account, error: accErr } = await supabase
      .from("paper_accounts")
      .select("*")
      .eq("id", accountId)
      .single();
    if (accErr || !account) {
      return new Response(
        JSON.stringify({ error: "Cuenta paper no encontrada" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 404 }
      );
    }

    let feeConfig: FeeConfigRow & { id: number };
    if (body.fee_config_id) {
      const { data: fc, error: fcErr } = await supabase
        .from("fee_configs")
        .select("id, maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding")
        .eq("id", body.fee_config_id)
        .single();
      if (fcErr || !fc) {
        return new Response(
          JSON.stringify({ error: "Fee config no encontrado" }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
        );
      }
      feeConfig = fc as FeeConfigRow & { id: number };
    } else {
      const { data: fc, error: fcErr } = await supabase
        .from("fee_configs")
        .select("id, maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding")
        .eq("is_default", true)
        .limit(1)
        .single();
      if (fcErr || !fc) {
        return new Response(
          JSON.stringify({ error: "No hay fee config por defecto" }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
        );
      }
      feeConfig = fc as FeeConfigRow & { id: number };
    }

    const qty = Number(quantity);
    const entryPrice = Number(entry_price);
    const entryNotional = Math.round(qty * entryPrice * 10000) / 10000;
    const marginUsedUsdt = calcMarginUsed(entryNotional, Number(leverage));
    const makerTaker = (body.maker_taker_entry || "TAKER").toUpperCase() as MakerTaker;
    const rate = getFeeRate(
      Number(feeConfig.maker_fee_bps),
      Number(feeConfig.taker_fee_bps),
      makerTaker,
      Number(feeConfig.bnb_discount_pct)
    );
    const entryFee = calcEntryFee(entryNotional, rate);

    const available = Number(account.available_balance_usdt);
    const valid = validateAvailableCapital(available, marginUsedUsdt, entryFee);
    if (!valid.ok) {
      return new Response(
        JSON.stringify({ error: valid.reason }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    const capitalBefore = Number(account.current_balance_usdt);
    const now = new Date().toISOString();

    const tradeRow = {
      source: body.source ?? "manual",
      symbol,
      market: body.market ?? "usdt_m",
      strategy_family,
      strategy_name,
      strategy_version,
      strategy_id: null,
      timeframe,
      position_side: position_side.toUpperCase(),
      order_side_entry,
      order_type_entry: body.order_type_entry ?? "MARKET",
      maker_taker_entry: makerTaker,
      leverage: Number(leverage),
      quantity: qty,
      entry_price: entryPrice,
      take_profit: body.take_profit ?? null,
      stop_loss: body.stop_loss ?? null,
      signal_timestamp: null,
      strategy_params_json: null,
      notes: body.notes ?? null,
      exit_price: null,
      exit_order_type: null,
      maker_taker_exit: null,
      exit_reason: null,
      closed_at: null,
      entry_notional: entryNotional,
      exit_notional: null,
      entry_fee: entryFee,
      exit_fee: null,
      funding_fee: null,
      slippage_usdt: null,
      gross_pnl_usdt: null,
      net_pnl_usdt: null,
      pnl_pct_notional: null,
      pnl_pct_margin: null,
      account_id: accountId,
      signal_event_id: null,
      status: "OPEN",
      opened_at: now,
      margin_used_usdt: marginUsedUsdt,
      capital_before_usdt: capitalBefore,
      capital_after_usdt: null,
      fee_config_id: feeConfig.id,
      idempotency_key: null,
      risk_profile_id: body.risk_profile_id ?? null,
    };

    const { data: trade, error: tradeErr } = await supabase
      .from("trades")
      .insert(tradeRow)
      .select()
      .single();
    if (tradeErr) {
      return new Response(
        JSON.stringify({ error: "Error al crear trade: " + tradeErr.message }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
      );
    }

    const newUsedMargin = Number(account.used_margin_usdt) + marginUsedUsdt;
    const newCurrentBalance = Number(account.current_balance_usdt) - entryFee;
    const newTotalFees = Number(account.total_fees_usdt) + entryFee;
    const newAvailable = newCurrentBalance - newUsedMargin;

    await supabase
      .from("paper_accounts")
      .update({
        used_margin_usdt: newUsedMargin,
        current_balance_usdt: newCurrentBalance,
        total_fees_usdt: newTotalFees,
        available_balance_usdt: newAvailable,
        updated_at: now,
      })
      .eq("id", accountId);

    const balanceBefore = Number(account.current_balance_usdt);
    const balanceAfter = newCurrentBalance;
    await supabase.from("account_ledger").insert({
      account_id: accountId,
      trade_id: trade.id,
      backtest_run_id: null,
      event_type: "TRADE_OPEN",
      amount_usdt: -(marginUsedUsdt + entryFee),
      balance_before_usdt: balanceBefore,
      balance_after_usdt: balanceAfter,
      meta_json: JSON.stringify({ trade_id: trade.id, margin_used_usdt: marginUsedUsdt, entry_fee: entryFee }),
    });

    return new Response(JSON.stringify(trade), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 201,
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String(e) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    );
  }
});
