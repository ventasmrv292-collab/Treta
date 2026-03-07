# Diagnóstico: Pantalla de Analíticas vacía

## 1. Qué estaba fallando

- **Causa más probable**: No había **trades cerrados** en la base de datos con `closed_at` y `net_pnl_usdt` rellenados. La pantalla de Analíticas solo usa trades que cumplen eso; si no hay filas, las tablas y la curva salen vacías.
- **Otras causas posibles**:
  - **Frontend no conectado a Supabase**: Si `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` no están definidos, el frontend llama al backend FastAPI; si ese backend no expone analíticas o falla, se ve vacío.
  - **Error en la llamada**: Si la Edge Function `get-analytics` falla (404, 500, CORS), el frontend hacía `.catch(() => {})` y no mostraba error, solo “Sin datos”.
  - **Filtro por estado**: La lógica usa trades con `closed_at IS NOT NULL` y `net_pnl_usdt IS NOT NULL`. Si los cierres no actualizan bien `closed_at` o `net_pnl_usdt`, no entran en analíticas.

## 2. Qué se ha hecho

| Problema | Solución |
|----------|----------|
| Sin datos de ejemplo | Seed opcional `003_analytics_sample_data.sql` con 6 trades cerrados y 1 backtest run con curva. |
| Lógica solo en Edge Function | Vistas SQL y RPC `get_analytics()` para que la fuente de verdad sea la base. |
| Errores silenciados | Pantalla de Analíticas muestra error y botón “Reintentar” cuando falla la petición. |
| Estados vacíos poco claros | Mensajes específicos por bloque: estrategia, apalancamiento, curva. |
| Falta de resumen backtest | Vista `analytics_backtest_summary` para capital inicial/final, drawdown, profit factor, retorno %. |

## 3. Tablas que alimentan cada bloque

| Bloque en la UI | Fuente de datos | Condición |
|-----------------|-----------------|-----------|
| **PnL por estrategia** | `trades` (cerrados) | `closed_at IS NOT NULL` y `net_pnl_usdt IS NOT NULL`. Agrupado por `strategy_family` + `strategy_name`. |
| **Comparativa x10 vs x20** | `trades` (cerrados) | Mismo filtro. Agrupado por `leverage`. |
| **Curva de equity** | `trades` (cerrados) | Mismo filtro. Ordenado por `closed_at`. Se usa la suma acumulada de `net_pnl_usdt`. |
| **Resumen backtest** (vista SQL) | `backtest_runs` | `status = 'completed'` y `final_capital IS NOT NULL`. La pantalla actual no lo pinta; la vista está lista por si se añade una sección. |

## 4. Vistas y RPC creados

- **`analytics_by_strategy`**: Por estrategia: total_trades, total_net_pnl, avg_net_pnl, total_gross_pnl, total_fees, win_rate, profit_factor, avg_win, avg_loss.
- **`analytics_by_leverage`**: Por apalancamiento: total_trades, total_net_pnl, avg_net_pnl, total_fees, win_rate.
- **`analytics_equity_curve`**: Por trade cerrado: `closed_at`, `cumulative_net_pnl` (ventana acumulada).
- **`analytics_summary`**: Una fila: total_closed_trades, total_net_pnl, total_fees, win_rate, best_strategy, best_leverage.
- **`get_analytics()`**: RPC que devuelve en un solo JSON: by_strategy, by_leverage, equity_curve, summary.
- **`analytics_backtest_summary`**: Por backtest completado: run_id, strategy_name, initial_capital, final_capital, net_pnl, total_trades, win_rate, profit_factor, drawdown_pct, return_pct.

## 5. Flujo de datos actual

1. **Frontend** (`Analytics.tsx`) llama a `fetchAnalytics()`.
2. Con Supabase: `fetchAnalytics()` hace GET a la Edge Function `get-analytics`.
3. **Edge Function** `get-analytics`:
   - Intenta primero `supabase.rpc('get_analytics')` y mapea el resultado al formato que espera el frontend (strings para importes, etc.).
   - Si el RPC no existe o falla, hace fallback: lee `trades` con el filtro de cerrados y calcula en JS byStrategy, byLeverage y curva.
4. **Frontend** muestra los tres bloques; si la respuesta está vacía, muestra los mensajes de “sin datos” por sección; si la petición falla, muestra el error y “Reintentar”.

## 6. Cómo comprobar que funciona

1. **Migración**: Ejecutar `supabase/migrations/20250307100000_analytics_views.sql` en el proyecto Supabase (SQL Editor o `supabase db push`).
2. **Seed de ejemplo** (opcional): Ejecutar `supabase/seeds/003_analytics_sample_data.sql` en el SQL Editor para tener 6 trades cerrados y 1 backtest.
3. **Variables de entorno**: En el frontend, definir `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` para que use Supabase.
4. **Edge Function**: Tener desplegada la función `get-analytics` (usa el RPC si existe; si no, el fallback por trades).
5. Abrir la pantalla Analíticas: deberías ver tabla por estrategia, tarjetas x10/x20 y curva. Si no hay datos, solo mensajes de “sin datos” por bloque; si hay error de red/backend, mensaje de error y “Reintentar”.

## 7. Resumen

- **Qué fallaba**: Principalmente **falta de trades cerrados** con `closed_at` y `net_pnl_usdt`; además, errores de carga no se mostraban.
- **Qué faltaba**: Vistas/RPC en Supabase para analíticas, mensajes de error y vacío en la UI, y un seed opcional para pruebas.
- **Qué tablas alimentan qué**: Todo lo que ves en Analíticas (por estrategia, por leverage, curva) sale de **`trades`** con el filtro de cerrados; la vista de backtest sale de **`backtest_runs`** (y opcionalmente `backtest_equity_curve` si se añade esa sección en la UI).
