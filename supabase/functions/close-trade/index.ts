import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";

const BACKEND_URL = Deno.env.get("BACKEND_URL") || "http://localhost:8000";

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST" && req.method !== "PATCH") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }
  try {
    const body = await req.json();
    const tradeId = body.trade_id ?? body.tradeId;
    if (tradeId == null) {
      return new Response(JSON.stringify({ error: "trade_id required" }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 400,
      });
    }
    const { trade_id, ...rest } = body;
    const res = await fetch(`${BACKEND_URL}/api/v1/trades/${tradeId}/close`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rest),
    });
    const data = await res.json();
    return new Response(JSON.stringify(data), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: res.status,
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 500,
    });
  }
});
