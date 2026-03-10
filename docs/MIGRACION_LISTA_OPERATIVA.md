# Lista operativa de migración: n8n → backend

Asignación única por módulo, workflows n8n, checklist técnico y pruebas E2E.

---

## 1. MATRIZ DE RESPONSABILIDADES FINAL

Cada función tiene **un único responsable**. No hay “backend o supabase”.

| Función | Responsable | Detalle |
|--------|-------------|--------|
| **Base de datos (persistencia)** | **Supabase** | PostgreSQL. Tablas: trades, paper_accounts, account_ledger, signal_events, candles, strategies, fee_configs, risk_profiles, bot_logs, backtest_runs, backtest_results, backtest_equity_curve. Solo almacenamiento; la lógica no corre aquí. |
| **Sync de velas (1m, 5m, 15m)** | **Backend** | Scheduler jobs sync_candles_1m/5m/15m. Descarga de Binance y escritura en Supabase (tabla candles). |
| **Evaluación de estrategias** | **Backend** | Scheduler jobs run_strategies_1m/5m/15m. Lee estrategias activas y velas de Supabase, genera señales y abre trades en Supabase. |
| **Cierre por TP/SL** | **Backend** | Position supervisor (cada 15 s). Lee precio (price stream), actualiza PnL no realizado y cierra trades en Supabase. |
| **API de datos para la app** | **Backend** | Dashboard summary, listado de trades, analíticas (by-strategy, by-leverage, equity-curve), paper accounts, strategies, crear/cerrar trade, backtest. El backend lee/escribe en Supabase y expone REST. |
| **Estado scheduler y supervisor** | **Backend** | GET /api/v1/scheduler/status, GET /api/v1/supervisor/status. Solo el backend los expone. |
| **Precio en tiempo real y klines para la UI** | **Backend** | WebSocket de precio y GET market/price, market/klines. Solo el backend. |
| **Interfaz de usuario** | **Frontend** | React. **Debe consumir solo el backend** para dashboard, histórico, analíticas, trades, backtest (ver sección Frontend más abajo). |
| **Ingestión de señales externas** | **Backend** | POST /api/v1/webhook/n8n/trade. n8n (u otro sistema) envía la señal al backend; el backend valida y crea el trade en Supabase. |
| **Alertas, reportes, resumen diario** | **n8n** | n8n lee datos vía API del backend (dashboard-summary, analytics, bot_logs) y envía a Telegram/Discord/Slack/email. No ejecuta estrategias ni cierra trades. |
| **Backtest bajo demanda** | **n8n** (orquestador) | n8n llama a POST /api/v1/backtest del backend cuando el usuario o un cron lo pide. El backend ejecuta el backtest y escribe en Supabase. |

Resumen por módulo:

- **Backend:** Motor continuo (scheduler, supervisor, sync velas, estrategias) + API única para la app (dashboard, trades, analytics, backtest) + webhook de señales n8n. Lee y escribe en Supabase.
- **Supabase:** Solo base de datos (PostgreSQL). No expone lógica de negocio al frontend en esta arquitectura final.
- **Frontend:** Solo backend. Una sola fuente: `VITE_API_BASE_URL`. No usar Supabase como API de datos en producción para esta migración.
- **n8n:** Solo webhook de señales (→ backend), alertas/reportes (leyendo del backend) y disparar backtest (→ backend). Cero workflows continuos de precio, velas, estrategias o TP/SL.

---

## 2. LISTA DE WORKFLOWS N8N: DESACTIVAR / MANTENER / REEMPLAZAR

Nombres genéricos; ajusta al nombre real de cada workflow en tu n8n.

| Nombre del workflow (ejemplo) | Estado final | Motivo | Endpoint nuevo si aplica |
|------------------------------|--------------|--------|---------------------------|
| Sync velas 1m / Get candles 1m | **DESACTIVAR** | Backend ya sincroniza velas (sync_candles_1m cada 1 min). Evita duplicar escritura en `candles`. | — |
| Sync velas 5m / Get candles 5m | **DESACTIVAR** | Backend: sync_candles_5m cada 5 min. | — |
| Sync velas 15m / Get candles 15m | **DESACTIVAR** | Backend: sync_candles_15m cada 15 min. | — |
| Polling precio / Price ticker | **DESACTIVAR** | Backend tiene price stream y supervisor. No hace falta que n8n pida precio. | — |
| Estrategia breakout / Run strategy 1m | **DESACTIVAR** | Backend: run_strategies_1m. Evita doble apertura de trades. | — |
| Estrategia 5m / Run strategy 5m | **DESACTIVAR** | Backend: run_strategies_5m. | — |
| Estrategia 15m / Run strategy 15m | **DESACTIVAR** | Backend: run_strategies_15m. | — |
| Cerrar por TP/SL / Check TP SL | **DESACTIVAR** | Backend: position_supervisor cada 15 s. Evita doble cierre. | — |
| Calcular PnL / Update balance | **DESACTIVAR** | El backend actualiza cuenta y PnL al cerrar. n8n no debe ser fuente de verdad. | — |
| Webhook señales externas | **MANTENER** | Único flujo que debe abrir trades desde fuera. n8n solo reenvía el POST. | POST `{BACKEND_URL}/api/v1/webhook/n8n/trade` (mismo payload que hoy). |
| Resumen diario / Daily report | **MANTENER** | Solo notificación. Debe leer datos del backend, no calcular. | GET `{BACKEND_URL}/api/v1/dashboard/summary` o `GET /api/v1/analytics/dashboard-summary`. |
| Alertas trade abierto/cerrado | **MANTENER** | Notificación. Opcional: leer de bot_logs o webhook que dispare el backend. | GET `{BACKEND_URL}/api/v1/bot-logs`, o GET dashboard/summary. |
| Backtest bajo demanda | **REEMPLAZAR** | Sigue siendo workflow n8n, pero la llamada debe ir al backend, no a lógica dentro de n8n. | POST `{BACKEND_URL}/api/v1/backtest` con body (strategy_family, strategy_name, strategy_version, symbol, interval, start_time, end_time, initial_capital, leverage, etc.). |

Si tienes un solo workflow que hace “todo” (precio + velas + estrategias + TP/SL), ese workflow completo se **DESACTIVA** y se sustituye por el backend. Los flujos de “webhook señal”, “resumen” y “backtest” se mantienen o reemplazan como en la tabla.

---

## 3. CHECKLIST TÉCNICO DE MIGRACIÓN (orden exacto)

### Paso 1 – Desplegar y verificar backend

| # | Acción | Dónde | Qué comprobar |
|---|--------|--------|----------------|
| 1.1 | Desplegar backend (Railway/Render/local) con `DATABASE_URL` apuntando a Supabase | Backend | App arranca sin error. |
| 1.2 | Llamar a `GET /api/v1/scheduler/status` | Backend | Respuesta 200, `"running": true`, `"started_at"` numérico. |
| 1.3 | Esperar 1–2 min y volver a llamar `GET /api/v1/scheduler/status` | Backend | En `jobs` aparecen `sync_candles_1m`, `position_supervisor` con `last_run_at`. |
| 1.4 | Llamar a `GET /api/v1/supervisor/status` | Backend | `"running": true`, `last_cycle_at` reciente. |

### Paso 2 – Verificar sync de velas y tablas

| # | Acción | Dónde | Qué comprobar |
|---|--------|--------|----------------|
| 2.1 | Consultar tabla `candles` en Supabase | Supabase SQL / Table Editor | Filas con `symbol = 'BTCUSDT'`, `interval` en `1m`, `5m`, `15m`, `source = 'BINANCE'`. |
| 2.2 | Consultar tabla `bot_logs` | Supabase | Eventos `event_type = 'CANDLES_SYNC_OK'` con `context` (symbol, interval, count). |

### Paso 3 – Verificar estrategias y apertura de trades

| # | Acción | Dónde | Qué comprobar |
|---|--------|--------|----------------|
| 3.1 | Consultar tabla `strategies` | Supabase | Al menos una fila con `active = true` (p. ej. BREAKOUT/breakout_volume_v1/1.0.0). |
| 3.2 | Esperar al menos un ciclo de run_strategies_1m (p. ej. 2 min) | — | En `scheduler/status`, `jobs.run_strategies_1m.last_run_at` actualizado. |
| 3.3 | Consultar `signal_events` | Supabase | Si hay señal: filas con `source = 'BACKEND'`, `status` ACCEPTED o REJECTED. |
| 3.4 | Consultar `trades` | Supabase | Si hubo señal aceptada: fila con `source = 'BACKEND'`, `signal_event_id` no nulo. |
| 3.5 | Consultar `bot_logs` | Supabase | Eventos `STRATEGY_SIGNAL_CREATED`, `TRADE_OPENED` o `SIGNAL_REJECTED`. |

### Paso 4 – Unificar frontend a solo backend

| # | Acción | Dónde | Qué comprobar |
|---|--------|--------|----------------|
| 4.1 | En Vercel (o donde hospedes el frontend), definir **solo** `VITE_API_BASE_URL` con la URL del backend. **No** definir `VITE_SUPABASE_URL` ni `VITE_SUPABASE_ANON_KEY` para datos de trading. | Frontend env | Tras redeploy, la app usa solo el backend (USE_SUPABASE será false). |
| 4.2 | Redeploy del frontend | Vercel | Build correcto. |
| 4.3 | Abrir Dashboard en la app | Navegador | Resumen, scheduler y supervisor visibles; datos coherentes (mismos trades que en backend). |
| 4.4 | Abrir Histórico (trades) | Navegador | Lista de trades igual a la que devuelve `GET /api/v1/trades`. |
| 4.5 | Abrir Analíticas | Navegador | Por estrategia, por leverage y curva de equity con datos (los mismos que `GET /api/v1/analytics/by-strategy`, etc.). |

### Paso 5 – Desactivar workflows continuos en n8n

| # | Acción | Dónde | Qué comprobar |
|---|--------|--------|----------------|
| 5.1 | En n8n, desactivar (Active = Off) todos los workflows que hagan: sync velas, polling precio, ejecución de estrategias en bucle, cierre por TP/SL, cálculo de PnL/balance. | n8n | Esos workflows ya no se ejecutan. |
| 5.2 | Dejar activos solo: Webhook señales externas, Resumen diario (o alertas), Backtest bajo demanda (reemplazando la llamada por backend). | n8n | Solo se ejecutan estos. |

### Paso 6 – Comprobar que no hay duplicación

| # | Acción | Dónde | Qué comprobar |
|---|--------|--------|----------------|
| 6.1 | Revisar que en n8n no quede ningún trigger “Interval” o “Cron” que llame a Binance, escriba en `candles` o cierre trades. | n8n | Lista de workflows activos sin esos flujos. |
| 6.2 | En `bot_logs`, filtrar por `event_type` IN ('TP_HIT','SL_HIT','TRADE_CLOSED'). Comprobar que `module` sea 'supervisor' o 'trade_service' (backend). | Supabase | No hay cierres desde otra fuente. |
| 6.3 | En `trades`, comprobar que los `source = 'BACKEND'` no tengan “gemelo” con el mismo instante/estrategia abierto por n8n. | Supabase | Sin duplicados. |

---

## 4. PRUEBAS END-TO-END (resultado esperado)

Todas asumen que el frontend usa **solo backend** y que el backend está arrancado y conectado a Supabase.

### 4.1 Sync de velas

- **Acción:** Esperar 1–2 min con el backend en marcha.
- **Comprobar:** Tabla `candles`: nuevas filas BTCUSDT, interval 1m (y luego 5m/15m según intervalo).
- **Log:** `bot_logs` con `event_type = 'CANDLES_SYNC_OK'`, `module = 'candle_sync'`.
- **Resultado esperado:** Aumento del número de filas en `candles`; sin errores `CANDLES_SYNC_ERROR` de forma continuada.

### 4.2 Ejecución de estrategia 1m

- **Acción:** Tener velas 1m en `candles` (≥ 20) y al menos una estrategia activa; esperar 2 min.
- **Comprobar:** `GET /api/v1/scheduler/status` → `jobs.run_strategies_1m.last_run_at` actualizado.
- **Resultado esperado:** El job se ejecutó; si las condiciones de la estrategia se cumplen, aparece en `signal_events` (BACKEND) y quizá un trade en `trades` con `source = 'BACKEND'`.

### 4.3 Apertura de trade

- **Acción:** `POST /api/v1/trades` con body válido (symbol, strategy_family, strategy_name, strategy_version, timeframe, position_side, leverage, quantity, entry_price, take_profit, stop_loss, account_id si aplica).
- **Comprobar:** Respuesta 200 con objeto trade con `id`, `status = 'OPEN'`. En Supabase: nueva fila en `trades`, y en `paper_accounts` el `used_margin_usdt` y `current_balance_usdt` actualizados.
- **Resultado esperado:** Trade creado; cuenta actualizada; sin 400/500.

### 4.4 Rechazo por riesgo

- **Acción:** Configurar risk profile con `max_open_positions = 1` (o límite muy bajo). Abrir 1 trade manual. Disparar una señal (backend o n8n) que intentaría abrir otro trade en la misma cuenta.
- **Comprobar:** La segunda apertura falla (400 o respuesta de rechazo). En `signal_events` la fila con `status = 'REJECTED'`, `decision_reason` con texto de límite de riesgo. En `bot_logs`: `event_type = 'RISK_LIMIT_BLOCK'` o `'SIGNAL_REJECTED'`.
- **Resultado esperado:** No se crea segundo trade; señal rechazada y registrada.

### 4.5 Cierre por TP

- **Acción:** Abrir un trade LONG con `take_profit` = precio actual + 1 (o un valor que el precio vaya a alcanzar pronto). Esperar a que el precio llegue a TP (o simular en tests con mock de precio).
- **Comprobar:** En `trades` el registro con `closed_at` no nulo, `status = 'CLOSED'`, `exit_reason = 'take_profit'`, `net_pnl_usdt` rellenado. En `paper_accounts`: margen liberado, balance actualizado. En `bot_logs`: `event_type = 'TP_HIT'`, `module = 'supervisor'`.
- **Resultado esperado:** Un solo cierre por TP; cuenta y ledger coherentes.

### 4.6 Cierre por SL

- **Acción:** Igual que 4.5 pero con `stop_loss` alcanzado.
- **Comprobar:** `exit_reason = 'stop_loss'`, `status = 'CLOSED'`. En `bot_logs`: `event_type = 'SL_HIT'`.
- **Resultado esperado:** Un solo cierre por SL; PnL y cuenta correctos.

### 4.7 Actualización de analytics

- **Acción:** Tras tener al menos un trade cerrado, llamar a `GET /api/v1/analytics/by-strategy`, `GET /api/v1/analytics/by-leverage`, `GET /api/v1/analytics/equity-curve` y `GET /api/v1/dashboard/summary`.
- **Comprobar:** Respuestas 200 con datos (total_trades, win_rate, net_pnl, por estrategia, por leverage, puntos de curva). En la pantalla Analíticas de la app se ven los mismos datos.
- **Resultado esperado:** Analytics coherentes con los trades cerrados en Supabase; una sola fuente (backend).

### 4.8 Webhook externo desde n8n

- **Acción:** Desde n8n (o Postman), `POST {BACKEND_URL}/api/v1/webhook/n8n/trade` con body N8nTradeCreate (symbol, strategy_family, strategy_name, strategy_version, timeframe, position_side, leverage, entry_price, quantity, take_profit, stop_loss, account_id, idempotency_key).
- **Comprobar:** 200 y trade creado con `source = 'n8n'` (o el que envíes). En `signal_events` una fila con status ACCEPTED y `trade_id` asignado. Repetir con el mismo `idempotency_key`: rechazo o “duplicate”, no segundo trade.
- **Resultado esperado:** Un trade por señal; idempotencia correcta.

### 4.9 Backtest bajo demanda

- **Acción:** `POST {BACKEND_URL}/api/v1/backtest` con body (strategy_family, strategy_name, strategy_version, symbol, interval, start_time, end_time, initial_capital, leverage, etc.).
- **Comprobar:** 200 y respuesta con run (id o resultado). En Supabase: `backtest_runs` y `backtest_results` (y opcionalmente `backtest_equity_curve`) con el run_id.
- **Resultado esperado:** Un backtest ejecutado por el backend; datos en Supabase; n8n solo orquesta la llamada.

---

## Frontend: fuente de datos actual y unificación

### Estado actual del frontend

- **Sin** variables Supabase (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`): el frontend usa **solo backend** para todo (trades, dashboard, analíticas, paper accounts, strategies, create/close trade, backtest). Precio, klines, bot-logs, supervisor y scheduler **siempre** van al backend (no hay rama Supabase para ellos).
- **Con** variables Supabase definidas: el frontend usa **Supabase** (REST + Edge Functions) para: listado de trades, analíticas (get-analytics), dashboard summary (get-dashboard-summary), paper accounts, strategies, create trade (create-manual-trade), close trade (close-trade), run backtest (run-backtest). Sigue usando **backend** para: precio, klines, bot-logs, supervisor, scheduler (no hay equivalente en Supabase en este diseño).

Es decir: hoy no hay mocks; hay **dos modos**: solo backend, o híbrido (datos de trading en Supabase, resto en backend).

### Qué unificar para una sola fuente coherente

Para que **dashboard, histórico y analíticas** usen **una sola fuente** y alineado con la matriz de responsabilidades:

1. **Definir como fuente única el backend.**  
   En producción (Vercel u otro), configurar **solo**:
   - `VITE_API_BASE_URL` = URL del backend (ej. `https://tu-app.up.railway.app`).
   - **No** definir `VITE_SUPABASE_URL` ni `VITE_SUPABASE_ANON_KEY` para el frontend de trading.

2. **Consecuencia:**  
   `USE_SUPABASE` será `false`. Todas las llamadas de datos (fetchTrades, fetchDashboardSummary, fetchAnalytics, fetchPaperAccounts, fetchStrategies, createTrade, closeTrade, runBacktest) irán al backend. Dashboard, histórico y analíticas leerán **solo** del backend; una sola fuente coherente.

3. **Opcional (solo si más adelante quieres modo “sin backend”):**  
   Mantener el código que usa Supabase cuando las variables están definidas, pero **no** usar esas variables en el entorno de producción de esta migración. La asignación “oficial” para esta migración es: frontend → backend → Supabase (DB).

Resumen: para esta migración, **unificar = usar solo backend en el frontend** (solo `VITE_API_BASE_URL`, sin variables Supabase en el build de producción).
