# Cómo confirmar que todo funciona

Sigue estos pasos en orden. Si todos pasan, el flujo está bien.

---

## 1. GitHub Actions

1. En tu repo de GitHub ve a la pestaña **Actions**.
2. Deberías ver el workflow **"Deploy Supabase Edge Functions"**.
3. Si hiciste push a `main` (o ejecutaste el workflow a mano), abre el último run.
4. **Comprueba:** todos los pasos en verde (✓). Si alguno falla, abre el paso y revisa el error (secrets mal configurados, proyecto no enlazado, etc.).

---

## 2. Supabase: funciones desplegadas

1. Entra en [Supabase Dashboard](https://supabase.com/dashboard) → tu proyecto.
2. Menú izquierdo → **Edge Functions**.
3. **Comprueba:** aparecen las 6 funciones listadas (create-manual-trade, close-trade, ingest-signal-from-n8n, get-dashboard-summary, run-backtest, get-analytics). No debe salir "Deploy your first edge function".

---

## 3. Probar desde la web (frontend)

Tu web debe tener configuradas las variables de Supabase en el entorno donde corre (Vercel o local):

- `VITE_SUPABASE_URL` = `https://zgnplakatvpmhhczvkzv.supabase.co` (o tu project ref)
- `VITE_SUPABASE_ANON_KEY` = tu Anon key (Supabase → Project Settings → API → anon public)

Luego:

| Prueba | Dónde | Qué comprobar |
|--------|--------|----------------|
| **Dashboard** | Ir a la página principal / Dashboard | Se carga sin error; si hay cuenta y trades cerrados, ves resumen (total trades, PnL, etc.). |
| **Nueva operación** | Nueva operación → rellenar y enviar | Mensaje de éxito y el trade aparece en Histórico con estado abierto. |
| **Cerrar operación** | Histórico → elegir un trade abierto → Cerrar con precio y motivo | El trade pasa a cerrado y el balance de la cuenta se actualiza. |
| **Analíticas** | Ir a Analíticas | Si hay trades cerrados, ves "PnL por estrategia", "Comparativa x10 vs x20" y "Curva de equity" con datos (no "Sin datos"). |

Si algo falla, abre la consola del navegador (F12 → Console) y revisa si hay errores de red o mensajes al hacer la acción.

---

## 4. Probar un endpoint a mano (opcional)

Para confirmar que las funciones responden:

1. **Dashboard summary**  
   En el navegador o con Postman/curl (sustituye `TU_ANON_KEY` y, si usas cuenta, `1` por tu `account_id`):

   ```
   GET https://zgnplakatvpmhhczvkzv.supabase.co/functions/v1/get-dashboard-summary?account_id=1
   Header: Authorization: Bearer TU_ANON_KEY
   ```

   Debe devolver JSON con `total_trades`, `win_rate`, `net_pnl`, etc.

2. **Crear trade** (solo si quieres probar la función directo):

   ```
   POST https://zgnplakatvpmhhczvkzv.supabase.co/functions/v1/create-manual-trade
   Headers: Content-Type: application/json, Authorization: Bearer TU_ANON_KEY
   Body (JSON): { "symbol": "BTCUSDT", "strategy_family": "BREAKOUT", "strategy_name": "breakout_volume_v1", "strategy_version": "1.0.0", "timeframe": "15m", "position_side": "LONG", "order_side_entry": "BUY", "leverage": 10, "quantity": 0.001, "entry_price": 95000, "account_id": 1 }
   ```

   Debe devolver 201 y el objeto del trade creado.

Si estos dos responden bien, las funciones están desplegadas y accesibles.

---

## Resumen rápido

| Paso | Qué comprobar |
|------|----------------|
| 1 | Actions → workflow en verde |
| 2 | Supabase → Edge Functions → 6 funciones listadas |
| 3 | Web: Dashboard, nueva op., cerrar op., Analíticas con datos |
| 4 (opcional) | GET dashboard-summary y/o POST create-manual-trade devuelven JSON correcto |

Si 1 y 2 están bien pero la web falla, revisa que la URL y la Anon key de Supabase estén bien en el entorno (Vercel env vars o `.env` local).
