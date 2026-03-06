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

## Calidad y extensibilidad

- TypeScript estricto en frontend.
- Componentes reutilizables y servicios separados.
- Validación con Pydantic en backend.
- Seed con estrategias y operaciones mock.
- Diseño preparado para añadir más símbolos y estrategias.

## Licencia

Uso interno / educativo. No constituye asesoramiento financiero.
