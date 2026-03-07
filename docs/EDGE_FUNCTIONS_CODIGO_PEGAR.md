# Código de las Edge Functions para pegar en Supabase

En Supabase → **Edge Functions** → **Create new edge function**, crea **6 funciones** (una por sección). En cada una, **borra el código por defecto** y pega **solo** el bloque correspondiente.

---

## CORS (común a todas)

En cada función el encabezado CORS ya va incluido en el código. No hace falta crear un archivo aparte.

---

## 1. Función: `get-dashboard-summary`

Nombre al crear: **get-dashboard-summary**

```ts
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS, PATCH",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 405,
    });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseServiceKey);

  try {
    const url = new URL(req.url);
    const accountIdParam = url.searchParams.get("account_id");
    const accountId = accountIdParam ? parseInt(accountIdParam, 10) : null;

    const { data: closedTrades } = await supabase
      .from("trades")
      .select("id, net_pnl_usdt, gross_pnl_usdt, entry_fee, exit_fee, funding_fee, strategy_name, strategy_family, leverage")
      .not("closed_at", "is", null)
      .not("net_pnl_usdt", "is", null);

    const trades = closedTrades ?? [];
    const totalTrades = trades.length;
    const winners = trades.filter((t: { net_pnl_usdt: number }) => Number(t.net_pnl_usdt) > 0);
    const winningTrades = winners.length;
    const winRate = totalTrades ? Math.round((winningTrades / totalTrades) * 10000) / 100 : 0;

    let netPnl = 0, grossPnl = 0, totalFees = 0;
    for (const t of trades) {
      netPnl += Number(t.net_pnl_usdt ?? 0);
      grossPnl += Number(t.gross_pnl_usdt ?? 0);
      totalFees += Number(t.entry_fee ?? 0) + Number(t.exit_fee ?? 0) + Number(t.funding_fee ?? 0);
    }

    const winsSum = winners.reduce((s: number, t: { net_pnl_usdt: number }) => s + Number(t.net_pnl_usdt), 0);
    const lossesSum = trades.filter((t: { net_pnl_usdt: number }) => Number(t.net_pnl_usdt) < 0).reduce((s: number, t: { net_pnl_usdt: number }) => s + Number(t.net_pnl_usdt), 0);
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
        account = { id: acc.id, name: acc.name, base_currency: acc.base_currency, initial_balance_usdt: acc.initial_balance_usdt, current_balance_usdt: acc.current_balance_usdt, available_balance_usdt: acc.available_balance_usdt, used_margin_usdt: acc.used_margin_usdt, realized_pnl_usdt: acc.realized_pnl_usdt, unrealized_pnl_usdt: acc.unrealized_pnl_usdt, total_fees_usdt: acc.total_fees_usdt, status: acc.status };
        equityUsdt = String(Number(acc.current_balance_usdt) + Number(acc.unrealized_pnl_usdt ?? 0));
      }
      const { count } = await supabase.from("trades").select("id", { count: "exact", head: true }).eq("account_id", accountId).is("closed_at", null);
      openPositionsCount = count ?? 0;
    }

    const response = { btc_price: null, total_trades: totalTrades, win_rate: winRate, net_pnl: String(Math.round(netPnl * 10000) / 10000), gross_pnl: String(Math.round(grossPnl * 10000) / 10000), total_fees: String(Math.round(totalFees * 10000) / 10000), profit_factor: profitFactor, pnl_by_strategy, pnl_by_leverage, account, equity_usdt: equityUsdt, open_positions_count: openPositionsCount };

    return new Response(JSON.stringify(response), { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 });
  }
});
```

---

## 2. Función: `get-analytics`

Nombre al crear: **get-analytics**

```ts
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS, PATCH",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 405 });
  }

  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  try {
    const { data: trades, error: tradesErr } = await supabase
      .from("trades")
      .select("id, strategy_name, strategy_family, leverage, closed_at, net_pnl_usdt, gross_pnl_usdt, entry_fee, exit_fee")
      .not("closed_at", "is", null)
      .not("net_pnl_usdt", "is", null)
      .order("closed_at", { ascending: true });

    if (tradesErr) return new Response(JSON.stringify({ error: tradesErr.message }), { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 });

    const list = (trades ?? []) as { strategy_name: string; strategy_family: string; leverage: number; closed_at: string; net_pnl_usdt: number; gross_pnl_usdt: number; entry_fee: number; exit_fee: number }[];

    const byStrategyMap = new Map<string, { strategy_name: string; strategy_family: string; total_trades: number; net_pnl: number; gross_pnl: number; fees: number; wins: number; losses: number; wins_sum: number; losses_sum: number; avg_win_sum: number; avg_loss_sum: number }>();
    const byLeverageMap = new Map<number, { leverage: number; total_trades: number; net_pnl: number; fees: number; wins: number }>();

    for (const t of list) {
      const netPnl = Number(t.net_pnl_usdt ?? 0), grossPnl = Number(t.gross_pnl_usdt ?? 0), fees = Number(t.entry_fee ?? 0) + Number(t.exit_fee ?? 0);
      const key = `${t.strategy_family}|${t.strategy_name}`;
      const existing = byStrategyMap.get(key);
      if (existing) {
        existing.total_trades++; existing.net_pnl += netPnl; existing.gross_pnl += grossPnl; existing.fees += fees;
        if (netPnl > 0) { existing.wins++; existing.wins_sum += netPnl; existing.avg_win_sum += netPnl; }
        else { existing.losses++; existing.losses_sum += netPnl; existing.avg_loss_sum += netPnl; }
      } else {
        byStrategyMap.set(key, { strategy_name: t.strategy_name, strategy_family: t.strategy_family, total_trades: 1, net_pnl: netPnl, gross_pnl: grossPnl, fees, wins: netPnl > 0 ? 1 : 0, losses: netPnl <= 0 ? 1 : 0, wins_sum: netPnl > 0 ? netPnl : 0, losses_sum: netPnl <= 0 ? netPnl : 0, avg_win_sum: netPnl > 0 ? netPnl : 0, avg_loss_sum: netPnl <= 0 ? netPnl : 0 });
      }
      const lev = Number(t.leverage);
      const l = byLeverageMap.get(lev);
      if (l) { l.total_trades++; l.net_pnl += netPnl; l.fees += fees; if (netPnl > 0) l.wins++; }
      else byLeverageMap.set(lev, { leverage: lev, total_trades: 1, net_pnl: netPnl, fees, wins: netPnl > 0 ? 1 : 0 });
    }

    const byStrategy = Array.from(byStrategyMap.values()).map((s) => {
      const total = s.total_trades, winRate = total ? (s.wins / total) * 100 : 0, lossesAbs = Math.abs(s.losses_sum), profitFactor = lossesAbs ? s.wins_sum / lossesAbs : 0;
      const avgWin = s.wins ? s.avg_win_sum / s.wins : 0, avgLoss = s.losses ? s.avg_loss_sum / s.losses : 0, expectancy = total ? avgWin * (s.wins / total) + avgLoss * (s.losses / total) : 0;
      return { strategy_name: s.strategy_name, strategy_family: s.strategy_family, total_trades: s.total_trades, net_pnl: String(Math.round(s.net_pnl * 100) / 100), gross_pnl: String(Math.round(s.gross_pnl * 100) / 100), total_fees: String(Math.round(s.fees * 100) / 100), win_rate: Math.round(winRate * 100) / 100, profit_factor: Math.round(profitFactor * 10000) / 10000, avg_win: String(Math.round(avgWin * 100) / 100), avg_loss: String(Math.round(avgLoss * 100) / 100), expectancy: String(Math.round(expectancy * 100) / 100) };
    });

    const byLeverage = Array.from(byLeverageMap.values()).map((l) => {
      const total = l.total_trades, winRate = total ? (l.wins / total) * 100 : 0;
      return { leverage: l.leverage, total_trades: l.total_trades, net_pnl: String(Math.round(l.net_pnl * 100) / 100), win_rate: Math.round(winRate * 100) / 100, total_fees: String(Math.round(l.fees * 100) / 100) };
    });

    let cum = 0;
    const points = list.map((t) => { cum += Number(t.net_pnl_usdt ?? 0); return { time: t.closed_at ? new Date(t.closed_at).toISOString() : null, equity: Math.round(cum * 100) / 100 }; });

    return new Response(JSON.stringify({ byStrategy, byLeverage, equityCurve: { points } }), { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 });
  }
});
```

---

## 3–6. Resto de funciones (create-manual-trade, close-trade, ingest-signal-from-n8n, run-backtest)

Las funciones **create-manual-trade**, **close-trade**, **ingest-signal-from-n8n** y **run-backtest** son más largas y usan lógica de trading (fees, margen, PnL). El código está en tu repo en:

- `supabase/functions/create-manual-trade/index.ts`
- `supabase/functions/close-trade/index.ts`
- `supabase/functions/ingest-signal-from-n8n/index.ts`
- `supabase/functions/run-backtest/index.ts`

En el **editor de Supabase** no puedes usar la carpeta `_shared`, así que tienes dos opciones:

### Opción A – Desplegar con la CLI (recomendado)

Desde la carpeta del proyecto en tu PC:

```bash
cd "C:\Users\mviera\OneDrive - Groupe GM\PCsEquipment\MiguelViera\Desktop\Cripto"
supabase login
supabase link --project-ref zgnplakatvpmhhczvkzv
supabase functions deploy get-dashboard-summary --no-verify-jwt
supabase functions deploy get-analytics --no-verify-jwt
supabase functions deploy create-manual-trade --no-verify-jwt
supabase functions deploy close-trade --no-verify-jwt
supabase functions deploy ingest-signal-from-n8n --no-verify-jwt
supabase functions deploy run-backtest --no-verify-jwt
```

Así se usan los archivos del repo (con `_shared`) y no tienes que pegar nada en el editor.

### Opción B – Solo las 2 primeras en el editor

Puedes crear **solo** en el editor de Supabase:

1. **get-dashboard-summary** (código de la sección 1)
2. **get-analytics** (código de la sección 2)

Con eso el dashboard y las analíticas pueden funcionar. Para **crear/cerrar trades**, **n8n** y **backtest** hace falta desplegar las otras 4 con la CLI (Opción A).

---

## Resumen

| Función                 | Dónde obtener código                          | Cómo desplegar          |
|-------------------------|-----------------------------------------------|-------------------------|
| get-dashboard-summary   | Arriba en este doc (bloque 1)                 | Pegar en editor o CLI   |
| get-analytics           | Arriba en este doc (bloque 2)                 | Pegar en editor o CLI   |
| create-manual-trade     | `supabase/functions/create-manual-trade/`    | Solo CLI               |
| close-trade             | `supabase/functions/close-trade/`             | Solo CLI               |
| ingest-signal-from-n8n  | `supabase/functions/ingest-signal-from-n8n/` | Solo CLI               |
| run-backtest            | `supabase/functions/run-backtest/`           | Solo CLI               |

Si quieres, en el siguiente mensaje puedo dejarte el código completo autocontenido (con la lógica de trading inline) para **create-manual-trade** y **close-trade** y lo añadimos a este mismo documento para pegarlo en el editor.
