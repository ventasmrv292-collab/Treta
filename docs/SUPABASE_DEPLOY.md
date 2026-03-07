# Despliegue Supabase – Paper Trading BTCUSDT

Pasos para dejar la app funcionando end-to-end con Supabase como backend.

---

## 1. Archivos SQL a ejecutar en Supabase

En el **SQL Editor** del proyecto Supabase, ejecuta en este orden:

| Orden | Archivo | Descripción |
|-------|---------|-------------|
| 1 | `supabase/migrations/20250307000000_initial_schema.sql` | Tablas base: strategies, fee_configs, trades, candles, backtest_runs, backtest_results, triggers |
| 2 | `supabase/migrations/20250307000001_new_tables.sql` | paper_accounts, signal_events, backtest_equity_curve, account_ledger |
| 3 | `supabase/migrations/20250307000002_alter_trades.sql` | Columnas en trades: account_id, signal_event_id, status, opened_at, margin_used_usdt, capital_before/after, fee_config_id, idempotency_key |
| 4 | `supabase/migrations/20250307000003_alter_backtest_candles_strategies_fee.sql` | backtest_runs (strategy_id, fee_config_id, final_capital, peak/min_equity, total_funding/slippage, used_margin_peak), candles (close_time, is_closed, source), unique strategies/fee_configs |
| 5 | `supabase/migrations/20250307000004_rls.sql` | RLS en todas las tablas y políticas |
| 6 | `supabase/migrations/20250307000005_risk_profiles_bot_logs.sql` | risk_profiles, bot_logs |
| 7 | `supabase/migrations/20250307000006_trades_risk_profile.sql` | risk_profile_id en trades, default_risk_profile_id en paper_accounts |

Luego los **seeds** (una sola vez):

| Archivo | Descripción |
|---------|-------------|
| `supabase/seeds/001_initial_seed.sql` | Fee config por defecto, 3 estrategias (1.0.0), paper account 1000 USDT |
| `supabase/seeds/002_risk_profiles_seed.sql` | 3 risk profiles |

**Alternativa con CLI:** desde la raíz del repo:

```bash
npx supabase db push
```

y los seeds manualmente en SQL Editor copiando el contenido de `supabase/seeds/*.sql`.

---

## 2. Edge Functions

| Función | Método | Descripción |
|---------|--------|-------------|
| `create-manual-trade` | POST | Crea trade OPEN, actualiza paper_accounts, inserta ledger |
| `close-trade` | POST | Cierra trade, calcula PnL/fees, actualiza cuenta y ledger |
| `ingest-signal-from-n8n` | POST | Recibe señal n8n, guarda signal_events, abre trade o marca REJECTED |
| `get-dashboard-summary` | GET | Resumen: trades, win rate, PnL, fees, cuenta, equity, pnl por estrategia/leverage |
| `run-backtest` | POST | Crea backtest_run, lee candles, simula trade, guarda results y equity_curve |

### Desplegar cada función

Con Supabase CLI (instalar y `supabase login`):

```bash
# Desde la raíz del proyecto
cd supabase
supabase functions deploy create-manual-trade
supabase functions deploy close-trade
supabase functions deploy ingest-signal-from-n8n
supabase functions deploy get-dashboard-summary
supabase functions deploy run-backtest
```

O desde el Dashboard: **Edge Functions** → **New function** y pegar el código de cada carpeta `supabase/functions/<nombre>/index.ts` (y `_shared/cors.ts`, `_shared/trading.ts` como dependencias compartidas).

---

## 3. URLs y headers

- **Base URL:** `https://<PROJECT_REF>.supabase.co`
- **Edge Functions:** `https://<PROJECT_REF>.supabase.co/functions/v1/<nombre>`
- **REST (tablas):** `https://<PROJECT_REF>.supabase.co/rest/v1/<tabla>`

Headers para invocar Edge Functions (desde frontend o n8n):

```
Content-Type: application/json
Authorization: Bearer <SUPABASE_ANON_KEY>
```

(O usar `apikey: <SUPABASE_ANON_KEY>` si el cliente lo pide.)

---

## 4. Ejemplos de llamadas HTTP

### create-manual-trade (nueva operación)

```http
POST https://<PROJECT_REF>.supabase.co/functions/v1/create-manual-trade
Content-Type: application/json
Authorization: Bearer <ANON_KEY>

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

**Response 201:** objeto `trade` creado (id, status OPEN, margin_used_usdt, entry_fee, etc.).

---

### close-trade (cerrar operación)

```http
POST https://<PROJECT_REF>.supabase.co/functions/v1/close-trade
Content-Type: application/json
Authorization: Bearer <ANON_KEY>

{
  "trade_id": 1,
  "exit_price": 96000,
  "exit_order_type": "MARKET",
  "maker_taker_exit": "TAKER",
  "exit_reason": "take_profit"
}
```

**Response 200:** trade actualizado con exit_*, net_pnl_usdt, status CLOSED.

---

### get-dashboard-summary (dashboard)

```http
GET https://<PROJECT_REF>.supabase.co/functions/v1/get-dashboard-summary?account_id=1
Authorization: Bearer <ANON_KEY>
```

**Response 200:**

```json
{
  "total_trades": 5,
  "win_rate": 60,
  "net_pnl": "120.5",
  "gross_pnl": "125",
  "total_fees": "4.5",
  "profit_factor": 1.8,
  "pnl_by_strategy": [...],
  "pnl_by_leverage": [...],
  "account": { "id": 1, "current_balance_usdt": 1120.5, ... },
  "equity_usdt": "1120.5",
  "open_positions_count": 0
}
```

---

### ingest-signal-from-n8n (señales n8n)

```http
POST https://<PROJECT_REF>.supabase.co/functions/v1/ingest-signal-from-n8n
Content-Type: application/json
Authorization: Bearer <ANON_KEY>

{
  "symbol": "BTCUSDT",
  "strategy_family": "BREAKOUT",
  "strategy_name": "breakout_volume_v1",
  "strategy_version": "1.0.0",
  "timeframe": "15m",
  "position_side": "LONG",
  "leverage": 10,
  "entry_price": 95000,
  "quantity": 0.001,
  "account_id": 1,
  "idempotency_key": "n8n-abc-123"
}
```

**Response 200 (éxito):**

```json
{
  "status": "PROCESSED",
  "signal_event_id": 1,
  "trade_id": 1,
  "trade": { ... }
}
```

**Response 200 (duplicado):** `{ "status": "DUPLICATE", "signal_event_id": 1, "trade_id": 1 }`  
**Response 200 (rechazado):** `{ "status": "REJECTED", "signal_event_id": 1, "decision_reason": "..." }`

---

### run-backtest

```http
POST https://<PROJECT_REF>.supabase.co/functions/v1/run-backtest
Content-Type: application/json
Authorization: Bearer <ANON_KEY>

{
  "strategy_family": "BREAKOUT",
  "strategy_name": "breakout_volume_v1",
  "strategy_version": "1.0.0",
  "symbol": "BTCUSDT",
  "interval": "15m",
  "start_time": "2025-01-01T00:00:00Z",
  "end_time": "2025-01-31T23:59:59Z",
  "initial_capital": 1000,
  "leverage": 10,
  "fee_profile": "realistic",
  "slippage_bps": 5
}
```

**Response 200:** objeto `backtest_run` con status completed, total_trades, net_pnl, final_capital, etc.

**Nota:** `run-backtest` lee velas de la tabla `candles`. Si no hay filas para el símbolo/intervalo/rango de fechas, el backtest termina con 0 trades. Puedes poblar `candles` con un job o con el backend (market data).

---

## 5. Frontend con Supabase

En el proyecto React, configura en `.env` (o en Vercel/hosting):

```
VITE_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
VITE_SUPABASE_ANON_KEY=<tu_anon_key>
```

Si además usas backend FastAPI para precio/klines:

```
VITE_API_BASE_URL=https://tu-backend.render.com
```

Con `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` definidos, el frontend usará automáticamente:

- **Nueva operación** → `create-manual-trade`
- **Cerrar operación** → `close-trade`
- **Dashboard** → `get-dashboard-summary`
- **Backtest** → `run-backtest`
- Listado de trades, cuentas y estrategias vía REST de Supabase.

---

## 6. n8n – URL y headers

- **URL:** `https://<PROJECT_REF>.supabase.co/functions/v1/ingest-signal-from-n8n`
- **Método:** POST
- **Headers:**
  - `Content-Type`: `application/json`
  - `Authorization`: `Bearer <SUPABASE_ANON_KEY>`
- **Body:** JSON como en el ejemplo de “ingest-signal-from-n8n” (incluir `idempotency_key` para evitar duplicados).

---

## 7. Lista de verificación final

1. **Ejecutar migraciones** en el SQL Editor (archivos 00–06 en orden).
2. **Ejecutar seeds** (001_initial_seed.sql, 002_risk_profiles_seed.sql).
3. **Desplegar Edge Functions** (create-manual-trade, close-trade, ingest-signal-from-n8n, get-dashboard-summary, run-backtest).
4. **Probar create-manual-trade:** POST con body de ejemplo; comprobar trade OPEN y saldo de paper_accounts.
5. **Probar close-trade:** POST con trade_id y exit_price; comprobar trade CLOSED y PnL en cuenta.
6. **Probar ingest-signal-from-n8n:** POST desde n8n o Postman; comprobar signal_events y trade creado o REJECTED/DUPLICATE.
7. **Probar dashboard:** GET get-dashboard-summary?account_id=1; comprobar total_trades, win_rate, net_pnl, account.
8. **Probar backtest:** POST run-backtest con rango de fechas; comprobar backtest_runs y backtest_results (y backtest_equity_curve si aplica).

Completando estos pasos la app queda lista para funcionar end-to-end con Supabase.
