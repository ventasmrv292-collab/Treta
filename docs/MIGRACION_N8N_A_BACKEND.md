# Plan de migración: automatización continua de n8n al backend

Objetivo: dejar de usar n8n para la **automatización continua** (velas, estrategias, TP/SL) y usar solo el backend FastAPI, sin romper la app ni duplicar ejecución.

---

## Resumen rápido

| Responsable antes | Responsable después | Acción en n8n |
|-------------------|--------------------|----------------|
| n8n: polling precio / velas | Backend: sync_candles_1m/5m/15m | **Desactivar** workflows que obtengan velas o precio en bucle |
| n8n: evaluar estrategias y abrir trades | Backend: run_strategies_1m/5m/15m | **Desactivar** workflows que ejecuten estrategias en bucle |
| n8n: cerrar por TP/SL | Backend: position_supervisor (cada 15 s) | **Desactivar** workflows que cierren trades por precio |
| n8n: webhook señales externas | n8n o Supabase Edge Function | **Mantener** (solo ingestión de señales externas) |
| n8n: alertas / reportes / IA | n8n | **Mantener** (opcional) |
| n8n: lanzar backtest bajo demanda | Backend API o Supabase | **Reemplazar** por llamada a API; mantener workflow pero que llame al backend/Supabase |

---

## Fase 0: Inventario de workflows n8n (hazlo tú)

Antes de tocar nada, lista tus workflows en n8n y clasifícalos:

1. **Workflows que hacen algo cada X segundos/minutos de forma continua**
   - Ejemplos: “Cada 1 min obtener precio”, “Cada 5 min obtener velas”, “Cada 15 s revisar TP/SL”, “Cada minuto ejecutar estrategia”.
   - Estos son los que **duplican** al backend → hay que **desactivarlos** (o eliminarlos) en la migración.

2. **Workflows que se ejecutan por evento (webhook, cron diario, manual)**
   - Ejemplos: “Webhook para señales externas”, “Resumen diario a Telegram”, “Lanzar backtest cuando yo pulse”.
   - Estos **no duplican** la lógica continua → se **mantienen** (solo cambiar a qué API llaman si hace falta).

3. **Workflows que calculan PnL o “estado oficial” del trading**
   - Si n8n es la única fuente de “cuánto gano/pierdo” o “balance”, hay que dejar de usarla para eso y usar solo backend (o Supabase) como fuente de verdad.

Anota algo como:

```
Workflow A: "Sync velas 1m"     → Trigger: cada 1 min  → DESACTIVAR
Workflow B: "Estrategia breakout" → Trigger: cada 5 min → DESACTIVAR
Workflow C: "Cerrar por TP/SL"   → Trigger: cada 15 s   → DESACTIVAR
Workflow D: "Webhook señales"    → Trigger: webhook     → MANTENER
Workflow E: "Resumen diario"    → Trigger: 0 9 * * *   → MANTENER
```

---

## Fase 1: Qué desactivar en n8n

**Desactiva (o elimina) cualquier workflow que:**

- Haga **polling de precio** (cada pocos segundos o cada minuto) para “mantener precio al día”.
- **Descargue velas** (Binance u otro) en bucle y las guarde o las use para decidir.
- **Evalúe estrategias** en bucle (breakout, mean reversion, etc.) y abra trades.
- **Cierre trades** cuando el precio toque TP o SL (comparar precio actual con TP/SL y llamar a “cerrar trade”).
- **Calcule PnL o balance** como “fuente oficial” y lo escriba en BD o en otro sistema (el backend ya hace esto al cerrar).

No hace falta borrarlos de golpe: **desactívalos** (toggle “Active” a off). Así, si algo falla en el backend, puedes volver a activarlos de forma controlada.

---

## Fase 2: Qué mantener activo en n8n

**Mantén activos (y adapta si hace falta) los workflows que:**

| Uso | Qué hace n8n | Endpoint / acción ahora |
|-----|----------------|-------------------------|
| **Señales externas** | Recibe webhook con señal (de otro bot, IA, etc.) y debe abrir un trade | Llamar a **Supabase Edge Function** `ingest-signal-from-n8n` o al **webhook del backend** si tienes uno. No evaluar estrategias ni precio dentro de n8n. |
| **Alertas** | Envía mensaje a Telegram/Discord/Slack cuando hay trade abierto/cerrado o resumen | Mantener. Opción: que lean de **bot_logs** o de un webhook que dispare el backend al cerrar/abrir (si lo implementas). |
| **Resumen diario/semanal** | Envía un resumen (trades del día, PnL, etc.) por email o chat | Mantener. Que obtengan datos de **GET /api/v1/analytics/dashboard-summary** o **GET /api/v1/dashboard/summary** (backend) o de Supabase si la app usa Supabase. |
| **Backtest bajo demanda** | Usuario o cron lanza un backtest y recibe resultado | Mantener el flujo; cambiar la llamada para que use **POST /api/v1/backtest** (backend) o la Edge Function `run-backtest` (Supabase). |
| **IA / reportes** | Análisis con IA, informes, etc. | Mantener. Que lean datos vía API (backend o Supabase), no que ejecuten estrategias ni cierren trades. |

Resumen: **n8n sigue siendo válido para orquestación, notificaciones y entrada de señales externas; deja de usarlo para “motor” continuo (precio, velas, estrategias, TP/SL).**

---

## Fase 3: Endpoints a usar ahora

La app puede estar usando **solo backend**, **solo Supabase (Edge Functions)**, o **híbrido**. Usa esta tabla según cómo tengas configurado el frontend.

### Si la app usa **backend (Railway u otro)** como API principal

| Acción | Endpoint a usar | Método |
|--------|------------------|--------|
| Resumen dashboard | `{BACKEND_URL}/api/v1/dashboard/summary?account_id={id}` | GET |
| Analíticas por estrategia | `{BACKEND_URL}/api/v1/analytics/by-strategy` | GET |
| Analíticas por leverage | `{BACKEND_URL}/api/v1/analytics/by-leverage` | GET |
| Curva de equity | `{BACKEND_URL}/api/v1/analytics/equity-curve` | GET |
| Estado del scheduler | `{BACKEND_URL}/api/v1/scheduler/status` | GET |
| Estado del supervisor | `{BACKEND_URL}/api/v1/supervisor/status` | GET |
| Crear trade manual | `{BACKEND_URL}/api/v1/trades` | POST |
| Cerrar trade | `{BACKEND_URL}/api/v1/trades/{id}/close` | PATCH |
| Listar estrategias activas | `{BACKEND_URL}/api/v1/strategies` | GET |
| Lanzar backtest | `{BACKEND_URL}/api/v1/backtest` | POST |
| Obtener resultado backtest | `{BACKEND_URL}/api/v1/backtest/{id}` | GET |

### Si la app usa **Supabase** (Edge Functions + REST)

| Acción | Endpoint a usar | Método |
|--------|------------------|--------|
| Resumen dashboard | `{SUPABASE_URL}/functions/v1/get-dashboard-summary?account_id={id}` | GET |
| Analíticas | `{SUPABASE_URL}/functions/v1/get-analytics` | GET |
| Crear trade manual | `{SUPABASE_URL}/functions/v1/create-manual-trade` | POST |
| Cerrar trade | `{SUPABASE_URL}/functions/v1/close-trade` | POST (body: trade_id, etc.) |
| Lanzar backtest | `{SUPABASE_URL}/functions/v1/run-backtest` | POST |
| Ingestar señal (n8n → Supabase) | `{SUPABASE_URL}/functions/v1/ingest-signal-from-n8n` | POST |

Para **scheduler y supervisor** no hay Edge Functions: esa lógica corre en el **backend**. Si usas solo Supabase sin backend, no tendrás cierre automático por TP/SL ni ejecución de estrategias en el backend; en ese caso o bien despliegas el backend para eso, o implementas esa lógica en Supabase (cron externo + Edge Function).

### n8n: qué URL usar en cada caso

- **Señales externas:**  
  - Si usas Supabase: llamar a `ingest-signal-from-n8n` con `Authorization: Bearer {SUPABASE_ANON_KEY}`.  
  - Si usas solo backend: necesitas un endpoint tipo `POST /api/v1/webhook/n8n/trade` (o el que tengas) con el mismo payload que antes.
- **Resumen / analytics:**  
  - Backend: `GET {BACKEND_URL}/api/v1/dashboard/summary`.  
  - Supabase: `GET {SUPABASE_URL}/functions/v1/get-dashboard-summary` (y get-analytics para detalle).
- **Backtest:**  
  - Backend: `POST {BACKEND_URL}/api/v1/backtest`.  
  - Supabase: `POST {SUPABASE_URL}/functions/v1/run-backtest`.

---

## Fase 4: Cómo probar cada parte

### 4.1 Backend arrancado y scheduler activo

1. Arranca el backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
2. `GET /api/v1/scheduler/status` → debe devolver `"running": true` y `started_at`.
3. Espera 1–2 minutos y vuelve a llamar: en `jobs` deberían aparecer `last_run_at` para `sync_candles_1m`, `position_supervisor`, etc.

### 4.2 Supervisor (TP/SL)

1. `GET /api/v1/supervisor/status` → `running: true`, `last_cycle_at` actualizándose cada ~15 s.
2. Abre un trade manual con TP/SL; simula que el precio toca TP o SL (o espera a que el precio real lo haga). Comprueba que el trade pasa a `CLOSED` y que en `bot_logs` hay `TP_HIT` o `SL_HIT`.

### 4.3 Sync de velas

1. En la base de datos, revisa la tabla `candles`: deben aparecer filas `symbol = 'BTCUSDT'`, `interval` en `1m`, `5m`, `15m`.
2. En `bot_logs` busca eventos `CANDLES_SYNC_OK` con `context` indicando symbol, interval y count.

### 4.4 Estrategias y apertura de trades

1. Comprueba que en `strategies` hay estrategias activas (p. ej. BREAKOUT/breakout_volume_v1, etc.).
2. Asegura que hay suficientes velas en `candles` para 1m (y 5m/15m si quieres probar).
3. Espera al menos un ciclo de `run_strategies_1m` (1 min + stagger). Busca en `signal_events` filas con `source = 'BACKEND'` y en `trades` con `source = 'BACKEND'` si hubo señal aceptada.
4. Revisa `bot_logs` para `STRATEGY_SIGNAL_CREATED`, `TRADE_OPENED` o `SIGNAL_REJECTED` / `RISK_LIMIT_BLOCK` si no se abre.

### 4.5 Dashboard y analíticas en la web

1. Abre el dashboard de la app: debe cargar resumen (total trades, win rate, PnL, cuenta si aplica).
2. Comprueba la sección “Scheduler” y “Supervisor (TP/SL)” con datos (si el frontend está apuntando al backend).
3. Entra en Analíticas: por estrategia, por leverage, curva de equity con datos reales (según endpoint que use la app: backend o Supabase).

### 4.6 n8n: webhook de señales (si lo usas)

1. Mantén **solo** el workflow de “ingestión de señal” activo.
2. Envía un POST de prueba al webhook (o a `ingest-signal-from-n8n`) con un payload válido y comprueba que se crea un trade o que `signal_events` tiene una nueva fila con status ACCEPTED/REJECTED y, si aplica, `trade_id`.

### 4.7 Backtest desde n8n (si lo usas)

1. Cambia el nodo que lanzaba backtest para que llame a `POST /api/v1/backtest` (backend) o a la Edge Function `run-backtest` (Supabase).
2. Ejecuta el workflow manualmente y verifica que recibes un resultado (run id, métricas) y que en BD existe el registro en `backtest_runs` / `backtest_results`.

---

## Fase 5: Cómo verificar que no hay duplicación

Objetivo: que **solo el backend** (o solo Supabase, según tu diseño) haga “motor continuo”; n8n no debe hacer lo mismo en paralelo.

### 5.1 Lista de comprobación

- [ ] **Precio / velas**  
  - En n8n no hay ningún workflow activo que, en bucle (cada X s/min), obtenga precio o velas de Binance (o similar).  
  - Comprobación: en n8n, todos los workflows con trigger “Interval” o “Cron” que toquen mercado están **desactivados** salvo los de resumen/backtest bajo demanda.

- [ ] **Evaluación de estrategias**  
  - En n8n no hay ningún workflow activo que, en bucle, “decida” abrir un trade según estrategia (breakout, mean reversion, etc.).  
  - Comprobación: solo el backend (o la Edge Function que tú designes) es quien crea trades con `source = 'BACKEND'` o equivalente; n8n solo crea trades vía “señal externa” (webhook → ingest).

- [ ] **Cierre por TP/SL**  
  - En n8n no hay ningún workflow activo que compare precio actual con TP/SL y llame a “cerrar trade”.  
  - Comprobación: en `bot_logs`, los eventos `TP_HIT` y `SL_HIT` tienen `module = 'supervisor'` (backend); no hay lógica equivalente activa en n8n.

- [ ] **Idempotencia**  
  - Las señales que llegan por webhook (n8n) usan `idempotency_key` en el payload.  
  - Comprobación: no se crean dos trades para la misma señal (mismo idempotency_key); en `signal_events` o en la respuesta del endpoint de ingest se ve “duplicate” o “rejected” si repites la misma llamada.

### 5.2 Comprobar en datos

- **Trades con `source = 'BACKEND'`**  
  - Son los abiertos por el motor del backend (estrategias). No deberían tener “gemelo” abierto por n8n en el mismo instante (misma estrategia, mismo timeframe). Puedes revisar por `created_at` y `strategy_name`/`timeframe`.

- **Trades con `source = 'n8n'` o `source = 'WEBHOOK'`**  
  - Son los abiertos por señal externa vía n8n. No debe haber un workflow en n8n que además, en bucle, abra trades por “estrategia interna”; solo ingestión de señales.

- **Cierres**  
  - Todos los cierres por TP/SL deberían venir del backend (supervisor). En `bot_logs`, `TRADE_CLOSED` con `module = 'trade_service'` y el flujo que dispara es el supervisor (que llama a `close_trade_and_compute_pnl`). No debería haber un flujo en n8n que cierre los mismos trades.

### 5.3 Resumen de “quién hace qué”

| Función | Quién lo hace | n8n |
|--------|----------------|-----|
| Obtener precio en tiempo real | Backend (price stream) | No |
| Sincronizar velas (1m, 5m, 15m) | Backend (scheduler) | No |
| Evaluar estrategias y abrir trades | Backend (scheduler) | No |
| Cerrar trades por TP/SL | Backend (supervisor) | No |
| Recibir señal externa y abrir 1 trade | Backend o Supabase (webhook / Edge Function) | Solo envía el POST |
| Resumen, alertas, reportes | Opcional en n8n | Sí (leyendo de API) |
| Backtest bajo demanda | Backend o Supabase | Solo llama al endpoint |

Si algo de la columna “n8n” sigue siendo “Sí” para las cuatro primeras filas, hay duplicación y hay que desactivar ese flujo en n8n.

---

## Orden sugerido de la migración

1. **Preparar**  
   - Dejar el backend desplegado y con scheduler/supervisor funcionando.  
   - Tener el documento de inventario de workflows n8n (Fase 0).

2. **Desactivar en n8n**  
   - Desactivar todos los workflows que hagan sync de velas, evaluación de estrategias o cierre por TP/SL (Fase 1).

3. **Comprobar backend**  
   - Verificar scheduler, supervisor, velas en DB, apertura/cierre de trades y analíticas (Fase 4).

4. **Ajustar n8n**  
   - Dejar activos solo webhook de señales, resumen, alertas, backtest bajo demanda (Fase 2).  
   - Actualizar URLs a los endpoints correctos (Fase 3).

5. **Verificar no duplicación**  
   - Revisar lista de comprobación y datos (Fase 5).

6. **Monitorear**  
   - Revisar `bot_logs` y trades durante unas horas/días para confirmar que no hay dobles aperturas ni cierres raros.

Si quieres, el siguiente paso puede ser bajar esto a tu lista concreta de nombres de workflows en n8n y marcar uno por uno “desactivar” / “mantener” y con qué endpoint reemplazar cada llamada.
