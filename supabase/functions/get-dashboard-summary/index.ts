import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { corsHeaders } from "../_shared/cors.ts";

const BACKEND_URL = Deno.env.get("BACKEND_URL") || "http://localhost:8000";

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const url = new URL(req.url);
    const accountId = url.searchParams.get("account_id");
    const backendUrl = `${BACKEND_URL}/api/v1/analytics/dashboard-summary${accountId ? `?account_id=${accountId}` : ""}`;
    const res = await fetch(backendUrl);
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
