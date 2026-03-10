# Checklist: poner en marcha el nuevo control (fees, runtime config, analíticas)

Sigue estos pasos **en orden** para que todo lo nuevo funcione.

---

## 1. Supabase (base de datos)

### 1.1 Migraciones

En el **SQL Editor** de Supabase ejecuta **en este orden**:

1. **`supabase/migrations/20250307210000_trades_quality_and_runtime.sql`**
   - Corrige trades CLOSED con datos faltantes.
   - Añade CHECKs de calidad (status vs closed_at/exit_price/net_pnl, backend → strategy_id).
   - Trigger para asignar `fee_config_id` por defecto.
   - Crea la tabla `strategy_runtime_config`.

2. **`supabase/migrations/20250307211000_advanced_analytics.sql`**
   - Crea las vistas: `analytics_by_strategy_tf_side`, `analytics_by_timeframe`, `analytics_by_side`, `analytics_by_profile`.

### 1.2 Seed de configuración

3. **`supabase/seeds/004_strategy_runtime_config_seed.sql`**
   - Inserta/actualiza la configuración inicial:
     - **Breakout:** activo en 1m, 5m, 15m; solo LONG; 15m con hasta 2 posiciones.
     - **VWAP:** 1m desactivado; 5m y 15m solo LONG, cooldown 5 min.
     - **EMA:** activo en 5m y 15m (LONG y SHORT).

Si alguna migración falla (por ejemplo por datos existentes que incumplen un CHECK), revisa el mensaje, corrige los datos en la tabla afectada y vuelve a ejecutar.

---

## 2. Backend (FastAPI / Railway)

### 2.1 Código ya incluido en el repo

- **`trade_service.py`**: `get_default_fee_config_id`, asignación de `fee_config_id` en manual y n8n, `has_exposure_conflict`, y en cierre relleno de `fee_config_id` si falta.
- **`strategy_engine.py`**: lectura de `strategy_runtime_config`, filtro por `active` / `allow_long` / `allow_short`, y comprobación de exposición/cooldown antes de abrir.
- **`models/strategy_runtime_config.py`**: modelo ORM.
- **`analytics_service.py`**: `get_runtime_recommendations`.
- **`api/routes/analytics.py`**: endpoint `GET /api/v1/analytics/runtime-recommendations?days=7`.

### 2.2 Despliegue

1. Haz **push** de los cambios al repositorio que usa Railway (o el que uses para el backend).
2. Espera a que el **deploy** termine sin errores.
3. Comprueba que el backend arranca (logs sin `ModuleNotFoundError` ni errores de import).

---

## 3. Frontend (Vercel u otro)

### 3.1 Código ya incluido

- **`api/endpoints.ts`**: `fetchRuntimeRecommendations`, endpoint `analytics.runtimeRecommendations(days)`.
- **`pages/Analytics.tsx`**: carga de recomendaciones y bloque de “Recomendaciones (últimos X días)” con mejor/peor estrategia y timeframe y lista de recomendaciones.
- **Locales**: claves `analytics.recommendationsTitle`, `bestStrategy`, `worstStrategy`, `bestTimeframe`, `worstTimeframe` en `es.json` y `pt-PT.json`.

### 3.2 Despliegue

1. Haz **push** al repo del frontend y deja que se despliegue (p. ej. Vercel).
2. Si usas variables de entorno (API URL, etc.), comprueba que estén bien configuradas en el proyecto de Vercel.

---

## 4. Comprobaciones rápidas

- **Trades con fee_config_id**  
  Después de abrir una operación (manual o por señal), en Supabase en `trades` la fila debe tener `fee_config_id` no nulo (si existe un fee config por defecto).

- **Runtime config**  
  En Supabase: `SELECT * FROM strategy_runtime_config;`  
  Debe haber filas por estrategia/timeframe con `active`, `allow_long`, `allow_short` y `cooldown_minutes` según el seed.

- **Señales rechazadas por exposición**  
  En los logs del backend (o en `bot_logs`) deberías ver eventos cuando una señal se rechaza por `EXPOSURE_LIMIT` o `COOLDOWN_ACTIVE`.

- **Recomendaciones en la web**  
  En la página **Analíticas**, arriba debe aparecer el bloque “Recomendaciones (últimos 7 días)” con mejores/peores estrategia y timeframe y la lista de recomendaciones (si el backend responde bien).

- **Endpoint de recomendaciones**  
  `GET https://TU_BACKEND/api/v1/analytics/runtime-recommendations?days=7`  
  Debe devolver JSON con `best_strategy`, `worst_strategy`, `recommendations`, etc.

---

## 5. Resumen de qué hace cada parte

| Parte | Qué hace |
|-------|----------|
| **Migración trades + trigger** | Asegura coherencia OPEN/CLOSED y rellena `fee_config_id` por defecto al insertar/actualizar. |
| **Tabla strategy_runtime_config** | Configura por estrategia/símbolo/timeframe: activar/desactivar, LONG/SHORT, max posiciones, cooldown. |
| **Seed 004** | Deja aplicado: VWAP sin 1m y sin SHORT; Breakout priorizado y 15m con 2 posiciones. |
| **Backend fee_config_id** | En alta y cierre de trades asigna siempre el fee config por defecto si existe. |
| **Backend has_exposure_conflict** | Impide abrir más de N posiciones por estrategia+side y respeta cooldown por timeframe. |
| **Backend strategy_engine** | Solo ejecuta señales si la config está activa y permite ese lado (LONG/SHORT), y si no hay conflicto de exposición. |
| **Analytics runtime-recommendations** | Calcula mejor/peor estrategia y timeframe y sugiere acciones (ej. desactivar SHORT, priorizar 15m). |
| **Frontend Analytics** | Muestra la tarjeta de recomendaciones y llama al backend para rellenarla. |

Si algo no cuadra (por ejemplo no se rellena `fee_config_id` o no ves recomendaciones), revisa en este orden: 1) migraciones y seed ejecutados, 2) backend desplegado y sin errores, 3) frontend apuntando a la URL correcta del backend y 4) que exista al menos un fee config por defecto y trades cerrados recientes para que las recomendaciones tengan datos.
