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

interface N8nSignalBody {
  symbol?: string;
  market?: string;
  strategy_family?: string;
  strategy_name?: string;
  strategy_version?: string;
  timeframe?: string;
  position_side?: string;
  leverage?: number;
  entry_price?: number;
  quantity?: number;
  take_profit?: number | null;
  stop_loss?: number | null;
  entry_order_type?: string;
  maker_taker_entry?: string;
  signal_timestamp?: string;
  strategy_params_json?: string | null;
  notes?: string | null;
  account_id?: number | null;
  risk_profile_id?: number | null;
  idempotency_key?: string | null;
  external_id?: string | null;
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
    const body = (await req.json()) as N8nSignalBody;
    const idempotencyKey = body.idempotency_key?.trim() || null;

    if (idempotencyKey) {
      const { data: existing } = await supabase
        .from("signal_events")
        .select("id, status, trade_id")
        .eq("idempotency_key", idempotencyKey)
        .limit(1)
        .single();
      if (existing) {
        return new Response(
          JSON.stringify({
            status: "DUPLICATE",
            message: "Señal ya procesada (idempotency_key)",
            signal_event_id: existing.id,
            trade_id: existing.trade_id,
          }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
        );
      }
    }

    const symbol = body.symbol ?? "BTCUSDT";
    const strategy_family = body.strategy_family ?? "";
    const strategy_name = body.strategy_name ?? "";
    const strategy_version = body.strategy_version ?? "1.0.0";
    const timeframe = body.timeframe ?? "15m";
    const position_side = (body.position_side ?? "LONG").toUpperCase();
    const leverage = Number(body.leverage ?? 10);
    const entry_price = Number(body.entry_price ?? 0);
    const quantity = Number(body.quantity ?? 0);

    if (!strategy_family || !strategy_name || entry_price <= 0 || quantity <= 0 || leverage < 1) {
      const signalRow = {
        source: "n8n",
        external_id: body.external_id ?? null,
        idempotency_key: idempotencyKey,
        symbol,
        timeframe,
        strategy_family: strategy_family || "UNKNOWN",
        strategy_name: strategy_name || "UNKNOWN",
        strategy_version,
        payload_json: JSON.stringify(body),
        status: "REJECTED",
        decision_reason: "Payload inválido: faltan strategy_family, strategy_name, entry_price, quantity o leverage",
        trade_id: null,
        processed_at: new Date().toISOString(),
      };
      const { data: ev } = await supabase.from("signal_events").insert(signalRow).select("id").single();
      return new Response(
        JSON.stringify({
          status: "REJECTED",
          signal_event_id: ev?.id,
          decision_reason: signalRow.decision_reason,
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    const payloadJson = JSON.stringify(body);
    const { data: signalEvent, error: sigErr } = await supabase
      .from("signal_events")
      .insert({
        source: "n8n",
        external_id: body.external_id ?? null,
        idempotency_key: idempotencyKey,
        symbol,
        timeframe,
        strategy_family,
        strategy_name,
        strategy_version,
        payload_json: payloadJson,
        status: "RECEIVED",
        decision_reason: null,
        trade_id: null,
        processed_at: null,
      })
      .select()
      .single();
    if (sigErr) {
      return new Response(
        JSON.stringify({ status: "ERROR", error: "Error al guardar signal_event: " + sigErr.message }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
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
      await supabase
        .from("signal_events")
        .update({ status: "REJECTED", decision_reason: "No hay cuenta paper activa", processed_at: new Date().toISOString() })
        .eq("id", signalEvent.id);
      return new Response(
        JSON.stringify({
          status: "REJECTED",
          signal_event_id: signalEvent.id,
          decision_reason: "No hay cuenta paper activa",
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    const { data: account } = await supabase.from("paper_accounts").select("*").eq("id", accountId).single();
    if (!account) {
      await supabase
        .from("signal_events")
        .update({ status: "REJECTED", decision_reason: "Cuenta paper no encontrada", processed_at: new Date().toISOString() })
        .eq("id", signalEvent.id);
      return new Response(
        JSON.stringify({ status: "REJECTED", signal_event_id: signalEvent.id, decision_reason: "Cuenta paper no encontrada" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    const { data: fc } = await supabase
      .from("fee_configs")
      .select("id, maker_fee_bps, taker_fee_bps, bnb_discount_pct, default_slippage_bps, include_funding")
      .eq("is_default", true)
      .limit(1)
      .single();
    const feeConfig = (fc ?? {
      id: null,
      maker_fee_bps: 2,
      taker_fee_bps: 4,
      bnb_discount_pct: 10,
      default_slippage_bps: 5,
      include_funding: true,
    }) as FeeConfigRow & { id: number | null };

    const entryNotional = Math.round(quantity * entry_price * 10000) / 10000;
    const marginUsedUsdt = calcMarginUsed(entryNotional, leverage);
    const makerTaker = (body.maker_taker_entry || "TAKER").toUpperCase() as MakerTaker;
    const rate = getFeeRate(
      Number(feeConfig.maker_fee_bps),
      Number(feeConfig.taker_fee_bps),
      makerTaker,
      Number(feeConfig.bnb_discount_pct)
    );
    const entryFee = calcEntryFee(entryNotional, rate);
    const valid = validateAvailableCapital(Number(account.available_balance_usdt), marginUsedUsdt, entryFee);
    if (!valid.ok) {
      await supabase
        .from("signal_events")
        .update({ status: "REJECTED", decision_reason: valid.reason ?? "Capital insuficiente", processed_at: new Date().toISOString() })
        .eq("id", signalEvent.id);
      return new Response(
        JSON.stringify({
          status: "REJECTED",
          signal_event_id: signalEvent.id,
          decision_reason: valid.reason ?? "Capital insuficiente",
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    const orderSideEntry = position_side === "LONG" ? "BUY" : "SELL";
    const capitalBefore = Number(account.current_balance_usdt);
    const now = new Date().toISOString();

    const tradeRow = {
      source: "n8n",
      symbol,
      market: body.market ?? "usdt_m",
      strategy_family,
      strategy_name,
      strategy_version,
      strategy_id: null,
      timeframe,
      position_side,
      order_side_entry: orderSideEntry,
      order_type_entry: body.entry_order_type ?? "MARKET",
      maker_taker_entry: makerTaker,
      leverage,
      quantity,
      entry_price,
      take_profit: body.take_profit ?? null,
      stop_loss: body.stop_loss ?? null,
      signal_timestamp: body.signal_timestamp ?? null,
      strategy_params_json: body.strategy_params_json ?? null,
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
      signal_event_id: signalEvent.id,
      status: "OPEN",
      opened_at: now,
      margin_used_usdt: marginUsedUsdt,
      capital_before_usdt: capitalBefore,
      capital_after_usdt: null,
      fee_config_id: feeConfig.id,
      idempotency_key: idempotencyKey,
      risk_profile_id: body.risk_profile_id ?? null,
    };

    const { data: trade, error: tradeErr } = await supabase
      .from("trades")
      .insert(tradeRow)
      .select()
      .single();
    if (tradeErr) {
      await supabase
        .from("signal_events")
        .update({
          status: "REJECTED",
          decision_reason: "Error al abrir trade: " + tradeErr.message,
          processed_at: new Date().toISOString(),
        })
        .eq("id", signalEvent.id);
      return new Response(
        JSON.stringify({
          status: "REJECTED",
          signal_event_id: signalEvent.id,
          decision_reason: "Error al abrir trade: " + tradeErr.message,
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
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

    await supabase.from("account_ledger").insert({
      account_id: accountId,
      trade_id: trade.id,
      backtest_run_id: null,
      event_type: "TRADE_OPEN",
      amount_usdt: -(marginUsedUsdt + entryFee),
      balance_before_usdt: capitalBefore,
      balance_after_usdt: newCurrentBalance,
      meta_json: JSON.stringify({ trade_id: trade.id, signal_event_id: signalEvent.id }),
    });

    await supabase
      .from("signal_events")
      .update({ status: "PROCESSED", trade_id: trade.id, processed_at: now })
      .eq("id", signalEvent.id);

    return new Response(
      JSON.stringify({
        status: "PROCESSED",
        signal_event_id: signalEvent.id,
        trade_id: trade.id,
        trade,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ status: "ERROR", error: String(e) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    );
  }
});
