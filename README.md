# Crypto Futures Sim — Paper Trading & Analytics

Aplicación web para **simulación y análisis** de operaciones de futuros de criptomonedas (paper trading). Centrada en **BTCUSDT perpetual** de Binance USD-M Futures. **No ejecuta órdenes reales** en ningún exchange.

## Características

- **Dashboard**: Gráfico de velas BTC en tiempo real, métricas (trades, win rate, PnL, fees), PnL por estrategia y por leverage.
- **Nueva operación manual**: Formulario para registrar entradas (símbolo, estrategia, timeframe, LONG/SHORT, leverage, entrada/salida, cierre con PnL calculado).
- **Webhook n8n**: Endpoint para recibir operaciones automáticas desde n8n.
- **Histórico**: Tabla con filtros, paginación, búsqueda (fechas, estrategia, leverage, manual/n8n, ganadoras/perdedoras).
- **Motor de fees y PnL**: Simulación de comisiones Binance Futures (maker/taker, BNB, slippage), perfiles conservador/realista/optimista, comparativa x10 vs x20.
- **Registro de estrategias**: BREAKOUT/breakout_volume_v1, MEAN_REVERSION/vwap_snapback_v1, TREND_PULLBACK/ema_pullback_v1.
- **Analíticas**: Comparativas por estrategia, familia, leverage, long/short; curva de equity; profit factor, win rate, etc.
- **Backtesting básico**: Ejecutar backtests por estrategia, timeframe, rango de fechas, leverage y perfil de fees.

## Stack

- **Frontend**: React 18 + TypeScript, Tailwind CSS, Vite, lightweight-charts (velas), React Router.
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy (async), PostgreSQL (asyncpg).
- **Datos de mercado**: Binance Futures API (solo lectura) para velas y precio.

## Estructura del proyecto

```
/frontend     # React + TS + Tailwind
/backend      # FastAPI + SQLAlchemy + servicios
/docs         # Documentación y ejemplos (API, schema DB, payload n8n)
```

## Requisitos

- Node.js 18+
- Python 3.11+
- PostgreSQL 14+

## Configuración

### 1. Base de datos

Crea una base de datos en PostgreSQL:

```bash
createdb crypto_sim
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edita .env y configura DATABASE_URL, por ejemplo:
# DATABASE_URL=postgresql+asyncpg://usuario:password@localhost:5432/crypto_sim
```

Crear tablas y datos iniciales (estrategias, fee configs, operaciones de ejemplo):

```bash
python scripts/seed.py
```

Iniciar la API:

```bash
python run.py
# o: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API quedará en **http://localhost:8000**. Documentación interactiva: **http://localhost:8000/docs**.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

La app quedará en **http://localhost:5173**. El proxy de Vite redirige `/api` al backend en el puerto 8000.

## Variables de entorno (backend)

| Variable | Descripción | Por defecto |
|---------|-------------|-------------|
| DATABASE_URL | PostgreSQL (async) | postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_sim |
| API_HOST | Host del servidor | 0.0.0.0 |
| API_PORT | Puerto | 8000 |
| DEBUG | Logs y CORS | true |
| CORS_ORIGINS | Orígenes permitidos | http://localhost:5173,http://127.0.0.1:5173 |
| BINANCE_FUTURES_REST_URL | API Binance Futures | https://fapi.binance.com |

## Webhook n8n

Para enviar operaciones desde n8n al backend:

- **URL**: `POST http://localhost:8000/api/v1/webhook/n8n/trade`
- **Body** (JSON): Ver ejemplo en `docs/n8n-webhook-payload.json`.

Campos esperados: `source` (n8n), `symbol`, `market`, `strategy_family`, `strategy_name`, `strategy_version`, `timeframe`, `position_side`, `leverage`, `entry_price`, `take_profit`, `stop_loss`, `quantity`, `entry_order_type`, `maker_taker_entry`, `signal_timestamp` (opcional), `strategy_params_json` (opcional), `notes` (opcional).

## Endpoints principales

- `GET /api/v1/market/price` — Precio actual BTC.
- `GET /api/v1/market/klines` — Velas para el gráfico.
- `GET /api/v1/trades` — Listado de operaciones (filtros y paginación).
- `POST /api/v1/trades` — Crear operación manual.
- `PATCH /api/v1/trades/{id}/close` — Cerrar operación (calcula fees y PnL).
- `POST /api/v1/webhook/n8n/trade` — Recibir operación desde n8n.
- `GET /api/v1/analytics/dashboard` — Métricas del dashboard.
- `GET /api/v1/analytics/by-strategy` — Comparativa por estrategia.
- `GET /api/v1/analytics/by-leverage` — Comparativa x10 vs x20.
- `POST /api/v1/backtest` — Ejecutar backtest.

Listado completo en `docs/api-endpoints.md`. Esquema de base de datos en `docs/database-schema.md`.

## Ampliación: Paper Trading con cuentas y ledger

El proyecto incluye una ampliación incremental para convertir la app en un **sistema de paper trading** con cuentas, ledger y señales n8n.

### Migraciones SQL (Supabase)

Ejecutar en el SQL Editor de Supabase **en este orden**:

1. **Esquema base** (si no existe): `docs/supabase-schema.sql`
2. **Nuevas tablas**: `docs/migrations/001_new_tables.sql` — `paper_accounts`, `account_ledger`, `signal_events`, `backtest_equity_curve`
3. **ALTER trades**: `docs/migrations/002_alter_trades.sql` — `account_id`, `status`, `margin_used_usdt`, etc.
4. **ALTER backtest/candles/strategies/fee_configs**: `docs/migrations/003_alter_backtest_candles_strategies_fee.sql`
5. **RLS**: `docs/migrations/004_rls.sql`
6. **Seed inicial**: `docs/seeds/001_initial_seed.sql` — una cuenta paper "Main Paper Account" (1000 USDT), fee config por defecto, 3 estrategias

### Nuevos endpoints

- `GET /api/v1/paper-accounts` — Lista cuentas paper
- `GET /api/v1/paper-accounts/{id}` — Detalle de cuenta
- `GET /api/v1/analytics/dashboard-summary?account_id=` — Resumen dashboard + métricas de cuenta (capital, equity, margen, fees)

### Edge Functions (Supabase)

Las Edge Functions en `supabase/functions/` actúan como proxy al backend. Configura la variable de entorno `BACKEND_URL` (URL de tu API, p. ej. Railway).

- **get-dashboard-summary** — GET con `?account_id=` opcional
- **create-manual-trade** — POST con body de creación de trade
- **close-trade** — POST/PATCH con body `{ trade_id, exit_price, exit_order_type, maker_taker_exit, exit_reason }`
- **ingest-signal-from-n8n** — POST con payload n8n
- **run-backtest** — POST con parámetros de backtest

Despliegue (CLI de Supabase):

```bash
supabase functions deploy get-dashboard-summary
supabase functions deploy create-manual-trade
supabase functions deploy close-trade
supabase functions deploy ingest-signal-from-n8n
supabase functions deploy run-backtest
```

### Lógica de negocio (backend)

- **`backend/app/services/trading_capital.py`**: `get_fee_rate`, `calc_entry_fee`, `calc_exit_fee`, `calc_gross_pnl`, `calc_net_pnl`, `calc_margin_used`, `validate_can_open_trade`
- La validación de margen y la actualización de `paper_accounts` y `account_ledger` al abrir/cerrar trades se pueden conectar en los endpoints de trades usando este módulo (próximo paso incremental).

### Flujo de prueba E2E

1. **Crear cuenta paper** — Ejecutar el seed; la cuenta "Main Paper Account" con 1000 USDT aparecerá en Dashboard (sección Cuenta Paper) y en el selector de Nueva operación.
2. **Abrir trade manual** — Ir a Nueva operación, seleccionar la cuenta, rellenar símbolo, estrategia, cantidad, precio; revisar el preview (notional, margen, fee, capital disponible); enviar.
3. **Cerrar trade** — En Histórico, filtrar y abrir una operación abierta; usar "Cerrar" e indicar precio de salida y motivo.
4. **Recibir señal n8n** — POST a `POST /api/v1/webhook/n8n/trade` (o a la Edge Function `ingest-signal-from-n8n`) con el JSON de ejemplo en `docs/n8n-webhook-payload.json`.
5. **Ejecutar backtest** — En la pestaña Backtest, elegir estrategia, rango de fechas, capital inicial y lanzar; revisar capital inicial/final, return %, peak equity y drawdown en la tabla.

## Calidad y extensibilidad

- TypeScript estricto en frontend.
- Componentes reutilizables y servicios separados.
- Validación con Pydantic en backend.
- Seed con estrategias y operaciones mock.
- Diseño preparado para añadir más símbolos y estrategias.

## Licencia

Uso interno / educativo. No constituye asesoramiento financiero.
