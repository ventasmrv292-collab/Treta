# Backend refactor: automatización continua sin n8n

El backend FastAPI es el **motor principal** del paper trading: sincroniza velas, ejecuta estrategias, abre/cierra trades y actualiza analytics. n8n queda como capa opcional (webhooks, IA, reportes).

---

## 1) Variables de entorno a configurar

Configura estas variables donde ejecutes el backend (local `.env`, Railway, Render, etc.):

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de PostgreSQL (Supabase: Connection string, Transaction pooler). El backend la lee como `database_url`. | `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres` |
| `PORT` | Puerto (en producción suele inyectarlo el host) | `8000` |
| `CORS_ORIGINS` | Orígenes permitidos (frontend) | `https://tu-app.vercel.app,http://localhost:5173` |
| `CORS_ALLOW_VERCEL_APP` | Si `true`, permite `*.vercel.app` | `true` |
| `BINANCE_FUTURES_REST_URL` | API Binance (o dejar default) | `https://fapi.binance.com` |
| `USE_BINANCE_FOR_MARKET` | Si en Render/host con 451, forzar Binance | `1` (opcional) |
| `USE_COINGECKO_FOR_MARKET` | Usar CoinGecko en lugar de Binance | `0` (solo si Binance da 451) |

Para **Supabase** usa la connection string del panel **Settings → Database** (modo Transaction si usas pooler).

---

## 2) Cómo arrancar el backend

```bash
cd backend
pip install -r requirements.txt   # o poetry install
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

En producción el host suele inyectar `PORT`; uvicorn lo usa si está definido en `app.config`.

Al arrancar:
- Se crean las tablas si no existen (`init_db`).
- Se inicia el **price stream** (WebSocket Binance para precio en tiempo real).
- Se inicia el **scheduler** (sync velas, estrategias, supervisor, analytics cache).

---

## 3) Cómo comprobar que corre el scheduler

- **API:** `GET /api/v1/scheduler/status`  
  Respuesta: `{ "running": true, "started_at": <timestamp>, "jobs": { "sync_candles_1m": { "last_run_at": ... }, ... } }`.
- **Dashboard web:** En la sección “Scheduler” debe aparecer “Activo” y, tras unos segundos/minutos, “Última sync velas 1m” y “Última estrategia 1m” con hora.
- **Logs:** En `bot_logs` debe haber un evento `SCHEDULER_STARTED` al arrancar.

---

## 4) Cómo comprobar que corre el supervisor

- **API:** `GET /api/v1/supervisor/status`  
  Respuesta: `{ "running": true, "last_cycle_at": <timestamp>, "check_interval_seconds": 15 }`.
- **Dashboard web:** En “Supervisor (TP/SL)” debe aparecer “Activo” y “Último: HH:mm:ss”.
- El supervisor se ejecuta cada 15 s dentro del scheduler; actualiza PnL no realizado y cierra trades por TP/SL.

---

## 5) Cómo comprobar que se sincronizan velas

- **Base de datos:** En la tabla `candles` deben aparecer filas con `symbol = 'BTCUSDT'`, `interval` en `1m`, `5m`, `15m`, `source = 'BINANCE'`.
- **Logs:** Eventos `CANDLES_SYNC_OK` en `bot_logs` con `context` `symbol`, `interval`, `count`.
- **API:** `GET /api/v1/candles?symbol=BTCUSDT&interval=1m` (si la ruta lee de DB) o que el scheduler no registre `CANDLES_SYNC_ERROR`.

---

## 6) Cómo comprobar que se abren trades

- Estrategias activas en tabla `strategies` (BREAKOUT/breakout_volume_v1, MEAN_REVERSION/vwap_snapback_v1, TREND_PULLBACK/ema_pullback_v1).
- Velas suficientes en `candles` para el timeframe (p. ej. ≥ 20 velas cerradas).
- Cuenta paper con balance y, si aplica, risk profile que permita abrir.
- En `trades` aparecen filas con `source = 'BACKEND'` y `signal_event_id` no nulo.
- En `signal_events` filas con `source = 'BACKEND'`, `status = 'ACCEPTED'` y `trade_id` asignado.
- Logs: `STRATEGY_SIGNAL_CREATED`, `TRADE_OPENED`.

Si no se abren: revisar `bot_logs` por `SIGNAL_REJECTED`, `RISK_LIMIT_BLOCK`, `DUPLICATE_SIGNAL` o falta de velas/capital.

---

## 7) Cómo comprobar que se cierran trades

- Trades con `take_profit` y/o `stop_loss` y precio que toque TP o SL (precio viene del price stream / Binance).
- En `trades`: `closed_at` y `status = 'CLOSED'`, `net_pnl_usdt` rellenado.
- En `paper_accounts`: `current_balance_usdt`, `used_margin_usdt`, `available_balance_usdt` actualizados.
- Logs: `TP_HIT` o `SL_HIT`, `TRADE_CLOSED`.

---

## 8) Cómo comprobar que la web muestra analíticas

- **Dashboard:** Resumen (total trades, win rate, net pnl, fees, cuenta) vía `GET /api/v1/analytics/dashboard-summary` o `GET /api/v1/dashboard/summary` (mismo contenido).
- **Analíticas:** Por estrategia y por leverage: `GET /api/v1/analytics/by-strategy`, `GET /api/v1/analytics/by-leverage`, `GET /api/v1/analytics/equity-curve`.
- Si el frontend usa **Supabase** para datos, configurar `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`; si usa solo backend, `VITE_API_BASE_URL` apuntando al backend.

---

## 9) Qué deja de hacer n8n y qué sigue haciendo

**Ya no debe hacer (lo hace el backend):**
- Polling de precio cada pocos segundos.
- Evaluar estrategias continuamente.
- Cerrar trades por TP/SL.
- Calcular el PnL oficial (lo hace el backend al cerrar).
- Sincronizar velas ni ser la fuente de verdad de trades.

**n8n puede seguir haciendo (opcional):**
- Webhook de señales externas → llamar a `ingest-signal-from-n8n` (Supabase) o al webhook del backend si existe.
- IA para análisis y reportes.
- Alertas a Telegram/Discord/Slack.
- Lanzar backtests bajo demanda (API backend o Supabase).
- Resumen diario/semanal por email o mensaje.
- Ingestión opcional de señales de terceros (registrando en `signal_events` y, si aplica, abriendo trade vía backend/Edge Function).

---

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/dashboard/summary` | Resumen dashboard (métricas + cuenta si `account_id`) |
| GET | `/api/v1/analytics/by-strategy` | Analíticas por estrategia |
| GET | `/api/v1/analytics/by-leverage` | Analíticas por leverage |
| GET | `/api/v1/analytics/equity-curve` | Curva de equity |
| GET | `/api/v1/supervisor/status` | Estado del supervisor TP/SL |
| GET | `/api/v1/scheduler/status` | Estado del scheduler y últimos runs |
| POST | `/api/v1/trades` | Crear trade manual |
| PATCH | `/api/v1/trades/{id}/close` | Cerrar trade |
| POST | `/api/v1/backtest` | Lanzar backtest |
| GET | `/api/v1/backtest/{id}` | Resultado de un backtest |
| GET | `/api/v1/strategies` | Lista estrategias (activas por defecto) |

---

## Checklist final (resumen)

1. **Variables de entorno:** `DATABASE_URL`, `PORT`, `CORS_ORIGINS` (y opcionales Binance/CoinGecko).
2. **Arrancar backend:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
3. **Scheduler:** `GET /api/v1/scheduler/status` → `running: true`; en dashboard web “Scheduler” activo.
4. **Supervisor:** `GET /api/v1/supervisor/status` → `running: true`; en dashboard “Supervisor (TP/SL)” activo.
5. **Velas:** Tabla `candles` con filas BTCUSDT 1m/5m/15m; logs `CANDLES_SYNC_OK`.
6. **Apertura de trades:** `strategies` activas, velas en DB, cuenta con balance; trades con `source = 'BACKEND'` y `signal_events` ACCEPTED.
7. **Cierre de trades:** TP/SL tocados; trades `CLOSED`; cuenta y ledger actualizados.
8. **Web y analíticas:** Dashboard y pantalla Analíticas con datos reales (backend o Supabase según config).
9. **n8n:** Sin polling/estrategias/cierre; solo webhooks, IA, alertas, backtests bajo demanda, reportes.
