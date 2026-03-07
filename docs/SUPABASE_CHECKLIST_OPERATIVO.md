# Checklist operativo Supabase – Paso a paso

Sustituye `TU_PROJECT_REF` por el ref de tu proyecto (ej: `abcdefghijklmnop`) y `TU_ANON_KEY` por tu Anon Key de Supabase.

---

## PARTE A: SQL en Supabase

**Dónde:** Dashboard Supabase → **SQL Editor** → New query.

**Orden obligatorio.** Ejecuta cada archivo **uno por uno** (copiar/pegar contenido y Run). Si ya tienes tablas creadas, algunos scripts pueden fallar en “already exists”; en ese caso ignora ese error o comenta la línea.

| Paso | Qué ejecutar | Archivo (ruta desde la raíz del repo) |
|------|----------------|----------------------------------------|
| A1 | Primera migración | `supabase/migrations/20250307000000_initial_schema.sql` |
| A2 | Segunda migración | `supabase/migrations/20250307000001_new_tables.sql` |
| A3 | Tercera migración | `supabase/migrations/20250307000002_alter_trades.sql` |
| A4 | Cuarta migración | `supabase/migrations/20250307000003_alter_backtest_candles_strategies_fee.sql` |
| A5 | Quinta migración (RLS) | `supabase/migrations/20250307000004_rls.sql` |
| A6 | Sexta migración | `supabase/migrations/20250307000005_risk_profiles_bot_logs.sql` |
| A7 | Séptima migración | `supabase/migrations/20250307000006_trades_risk_profile.sql` |
| A8 | Seed inicial | `supabase/seeds/001_initial_seed.sql` |
| A9 | Seed risk profiles | `supabase/seeds/002_risk_profiles_seed.sql` |

**Comprobar:** En **Table Editor** deben existir: `strategies`, `fee_configs`, `trades`, `candles`, `backtest_runs`, `backtest_results`, `paper_accounts`, `account_ledger`, `signal_events`, `backtest_equity_curve`, `risk_profiles`, `bot_logs`. Y en `paper_accounts` al menos una fila (Main Paper Account 1000 USDT).

---

## PARTE B: Secrets (variables de entorno)

**Dónde:** Dashboard Supabase → **Project Settings** → **Edge Functions** (o **Settings** → **Edge Functions**).

Las Edge Functions de este proyecto **solo usan** lo que Supabase inyecta por defecto:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

**No tienes que añadir ningún secret a mano.** Si en el futuro añades un backend externo u otra API, entonces sí configurarías secrets en esa misma pantalla.

---

## PARTE C: Desplegar Edge Functions

**Requisito:** Tener instalado [Supabase CLI](https://supabase.com/docs/guides/cli) y haber hecho `supabase login`.

**Dónde ejecutar:** En la raíz del proyecto (donde está la carpeta `supabase`).

```bash
# 1. Enlazar proyecto (solo la primera vez; pide project ref)
supabase link --project-ref TU_PROJECT_REF

# 2. Desplegar las 6 funciones (orden indistinto)
supabase functions deploy create-manual-trade
supabase functions deploy close-trade
supabase functions deploy ingest-signal-from-n8n
supabase functions deploy get-dashboard-summary
supabase functions deploy run-backtest
supabase functions deploy get-analytics
```

**Comprobar:** Dashboard → **Edge Functions**. Deben aparecer las 6 con estado “Deployed”.

---

## PARTE D: Endpoints que usarás desde n8n

Base URL de las funciones:

```
https://TU_PROJECT_REF.supabase.co/functions/v1
```

Headers en **todas** las peticiones desde n8n:

| Header | Valor |
|--------|--------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer TU_ANON_KEY` |

(En n8n suele usarse “Authorization” tipo “Bearer Token” con valor = tu Anon Key.)

Endpoints concretos:

| Uso en n8n | Método | URL completa |
|------------|--------|--------------|
| Crear trade manual | POST | `https://TU_PROJECT_REF.supabase.co/functions/v1/create-manual-trade` |
| Cerrar trade | POST | `https://TU_PROJECT_REF.supabase.co/functions/v1/close-trade` |
| Recibir señal (webhook n8n) | POST | `https://TU_PROJECT_REF.supabase.co/functions/v1/ingest-signal-from-n8n` |
| Resumen dashboard | GET | `https://TU_PROJECT_REF.supabase.co/functions/v1/get-dashboard-summary` |
| Ejecutar backtest | POST | `https://TU_PROJECT_REF.supabase.co/functions/v1/run-backtest` |

---

## PARTE E: Cómo probar cada endpoint

Usa Postman, Insomnia, o el nodo **HTTP Request** de n8n. Sustituye `TU_PROJECT_REF` y `TU_ANON_KEY`.

---

### E1 – create-manual-trade

- **URL:** `https://TU_PROJECT_REF.supabase.co/functions/v1/create-manual-trade`
- **Método:** POST
- **Headers:** `Content-Type: application/json`, `Authorization: Bearer TU_ANON_KEY`
- **Body (raw JSON):**

```json
{
  "symbol": "BTCUSDT",
  "market": "usdt_m",
  "strategy_family": "BREAKOUT",
  "strategy_name": "breakout_volume_v1",
  "strategy_version": "1.0.0",
  "timeframe": "15m",
  "position_side": "LONG",
  "order_side_entry": "BUY",
  "order_type_entry": "MARKET",
  "maker_taker_entry": "TAKER",
  "leverage": 10,
  "quantity": 0.001,
  "entry_price": 95000,
  "account_id": 1
}
```

**Éxito:** Status 201, body con objeto `trade` (incluye `id`, `status: "OPEN"`, `margin_used_usdt`, `entry_fee`).  
**Comprobar en Supabase:** Tabla `trades` → nueva fila; tabla `paper_accounts` → la cuenta `id=1` con `used_margin_usdt` y `available_balance_usdt` actualizados.

---

### E2 – close-trade

Solo si tienes un trade OPEN (por ejemplo el creado en E1). Usa su `id` como `trade_id`.

- **URL:** `https://TU_PROJECT_REF.supabase.co/functions/v1/close-trade`
- **Método:** POST
- **Headers:** igual que arriba
- **Body (raw JSON):**

```json
{
  "trade_id": 1,
  "exit_price": 96000,
  "exit_order_type": "MARKET",
  "maker_taker_exit": "TAKER",
  "exit_reason": "take_profit"
}
```

**Éxito:** Status 200, body con el trade actualizado (`status: "CLOSED"`, `exit_price`, `net_pnl_usdt`, etc.).  
**Comprobar en Supabase:** `trades` → esa fila con `closed_at` y `net_pnl_usdt`; `paper_accounts` → balance actualizado.

---

### E3 – ingest-signal-from-n8n (webhook de señales)

- **URL:** `https://TU_PROJECT_REF.supabase.co/functions/v1/ingest-signal-from-n8n`
- **Método:** POST
- **Headers:** igual que arriba
- **Body (raw JSON):**

```json
{
  "symbol": "BTCUSDT",
  "strategy_family": "BREAKOUT",
  "strategy_name": "breakout_volume_v1",
  "strategy_version": "1.0.0",
  "timeframe": "15m",
  "position_side": "LONG",
  "leverage": 10,
  "entry_price": 95500,
  "quantity": 0.001,
  "account_id": 1,
  "idempotency_key": "n8n-test-001"
}
```

**Éxito:** Status 200, body con `"status": "PROCESSED"`, `signal_event_id` y `trade_id`.  
**Duplicado (mismo idempotency_key):** Status 200, `"status": "DUPLICATE"`.  
**Rechazo (ej. sin cuenta):** Status 200, `"status": "REJECTED"`, `decision_reason` en el body.  
**Comprobar en Supabase:** `signal_events` → nueva fila; si procesado, `trades` → nuevo trade OPEN.

---

### E4 – get-dashboard-summary

- **URL:** `https://TU_PROJECT_REF.supabase.co/functions/v1/get-dashboard-summary?account_id=1`
- **Método:** GET
- **Headers:** `Authorization: Bearer TU_ANON_KEY` (no hace falta Content-Type en GET)

**Éxito:** Status 200, JSON con `total_trades`, `win_rate`, `net_pnl`, `total_fees`, `account`, `equity_usdt`, `open_positions_count`, `pnl_by_strategy`, `pnl_by_leverage`.

---

### E5 – run-backtest

- **URL:** `https://TU_PROJECT_REF.supabase.co/functions/v1/run-backtest`
- **Método:** POST
- **Headers:** igual que en E1
- **Body (raw JSON):**

```json
{
  "strategy_family": "BREAKOUT",
  "strategy_name": "breakout_volume_v1",
  "strategy_version": "1.0.0",
  "symbol": "BTCUSDT",
  "interval": "15m",
  "start_time": "2025-01-01T00:00:00.000Z",
  "end_time": "2025-01-31T23:59:59.000Z",
  "initial_capital": 1000,
  "leverage": 10,
  "fee_profile": "realistic",
  "slippage_bps": 5
}
```

**Éxito:** Status 200, body con el objeto del backtest (`status: "completed"`, `total_trades`, `net_pnl`, `final_capital`, etc.). Si la tabla `candles` está vacía para ese rango, el backtest puede terminar con 0 trades pero igual devuelve 200.

---

## Resumen checklist

- [ ] A1–A7: Ejecutar las 7 migraciones en orden en SQL Editor.
- [ ] A8–A9: Ejecutar los 2 seeds.
- [ ] Comprobar tablas y una fila en `paper_accounts`.
- [ ] B: Confirmar que no hace falta añadir secrets (solo las inyectadas por Supabase).
- [ ] C: `supabase link` y desplegar las 5 Edge Functions.
- [ ] D: Anotar en n8n las 5 URLs y los headers (Bearer + Anon Key).
- [ ] E1: Probar create-manual-trade (POST con body de ejemplo).
- [ ] E2: Probar close-trade (POST con trade_id del E1).
- [ ] E3: Probar ingest-signal-from-n8n (POST con body de ejemplo).
- [ ] E4: Probar get-dashboard-summary (GET con account_id=1).
- [ ] E5: Probar run-backtest (POST con body de ejemplo).

Con esto tienes todo lo que debes hacer manualmente en Supabase y cómo probar cada endpoint con ejemplos reales.
