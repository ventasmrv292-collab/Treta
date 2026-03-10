# Tabla `candles`: calidad, validación y flujo

## 1. Revisión del esquema actual

### Qué columnas ya existían
- `id`, `symbol`, `interval`, `open_time`, `open`, `high`, `low`, `close`, `volume`, `created_at`
- En migraciones previas: `close_time`, `is_closed`, `source`
- Índice único: `(symbol, interval, open_time)`

### Problemas del esquema anterior para trading y backtesting
- **Sin validación:** se podían insertar `volume = 0` o negativo, OHLC incoherente (high < low, etc.).
- **Sin garantía temporal:** no había comprobación de que `close_time - open_time` coincidiera con el intervalo (1m, 5m, 15m).
- **Ingesta:** el código podía usar CoinGecko como fallback, guardando velas diarias etiquetadas como 1m/15m.
- **Sin auditoría:** no había `ingested_at` ni `updated_at` ni estado de validación.
- **Campos Binance faltantes:** no se guardaban `quote_volume`, `trade_count`, `taker_buy_*`, ni `close_time` desde la API.

### Enfoque adoptado
- Una sola tabla canónica **`candles`** (no se crea `candles_raw`); la ingesta valida y escribe solo datos correctos.
- CHECKs y trigger en DB; validación también en el backend antes del insert.

---

## 2. Esquema mejorado (migraciones)

### Columnas existentes (antes de la migración)
- `id`, `symbol`, `interval`, `open_time`, `open`, `high`, `low`, `close`, `volume`, `created_at`
- Añadidas en migraciones previas: `close_time`, `is_closed`, `source`

### Columnas nuevas (migración `20250307200000_candles_quality_schema.sql`)
- `quote_volume`, `trade_count`, `taker_buy_base_volume`, `taker_buy_quote_volume` (Binance)
- `ingested_at`, `updated_at` (auditoría)
- `validation_status` ('PENDING' | 'VALID' | 'INVALID'), `validation_notes`

### Reglas de integridad
- **Unique:** `(symbol, interval, open_time)`
- **CHECK:** `interval IN ('1m','5m','15m','1h')`, `source IN ('BINANCE','COINGECKO','MANUAL','IMPORT')`
- **CHECK:** `volume >= 0`, `open/high/low/close > 0`, `high >= max(open,close,low)`, `low <= min(open,close,high)`
- **CHECK:** `close_time IS NULL OR open_time < close_time`
- **Trigger:** `close_time - open_time` debe coincidir con la duración del intervalo (±2 s)

## 3. Flujo de ingesta (backend)

1. **Origen:** Solo **Binance Futures** (`force_binance=True`). No se usa CoinGecko para guardar velas en DB (intervalos incorrectos).
2. **Filtro:** Solo se persisten velas **cerradas** (`close_time < now()`).
3. **Validación en código:** Antes de insertar se comprueba `volume >= 0`, OHLC positivo y coherente (high/low).
4. **Upsert:** Por `(symbol, interval, open_time)`. Se usa `close_time` y campos extra de la API cuando vienen.
5. **Base de datos:** Triggers y CHECKs evitan filas con intervalo temporal incorrecto o OHLC inválido.

## 4. Qué tabla consumen estrategias y backtest

- **Estrategias y backtest:** leen solo la tabla **`candles`** (canónica), filtrando `is_closed = true`.
- No se usa tabla `candles_raw`; todo se valida y guarda en `candles`.

## 5. Scripts

| Script | Uso |
|--------|-----|
| `docs/scripts/diagnose_candles.sql` | Diagnóstico: conteos de filas malas (volume=0, OHLC inválido, duplicados, intervalo incoherente). Solo lecturas. |
| `docs/scripts/repair_candles.sql` | Elimina filas inválidas y rellena `close_time` donde falte. Ejecutar antes de la migración si quieres reparar a mano. |
| `docs/scripts/backfill_candles.sql` | Plantilla para `DELETE`/`TRUNCATE` antes de reinyectar; la reingesta se hace con el backend. |

## 6. Función de control de calidad

En Supabase (o en el backend vía API):

- **SQL:** `SELECT public.get_candles_quality_report(NULL, NULL);` — devuelve JSON con `total_rows`, `zero_volume`, `invalid_ohlc`, `interval_mismatch`, `duplicates`, `temporal_gaps`, etc.
- **API:** `GET /api/v1/candles/quality?symbol=BTCUSDT&interval=1m` (requiere que la función RPC esté desplegada).

## 7. Checklist de verificación

- [ ] Migración `20250307200000_candles_quality_schema.sql` aplicada (columnas, CHECKs, triggers).
- [ ] Migración `20250307200001_candles_quality_function.sql` aplicada (función `get_candles_quality_report`).
- [ ] Backend usa `sync_candles_to_db` con `force_binance=True` y solo persiste velas cerradas.
- [ ] Ejecutar `diagnose_candles.sql` o `GET /api/v1/candles/quality`: sin inválidos o con plan de reparación.
- [ ] Si había datos malos: ejecutar `repair_candles.sql` o dejar que la migración borre inválidos; opcionalmente `backfill_candles.sql` + resincronizar con el backend.
- [ ] Estrategias y backtest leen de `candles` con `is_closed = true`.
