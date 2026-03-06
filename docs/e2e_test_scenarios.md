# Escenarios E2E para el Paper Trading Bot

Verifican que ledger, paper_accounts, trades y dashboard summary cuadran.

## Requisitos

- Backend en marcha (ej. `http://localhost:8000`)
- DB con migraciones 001–006 y seeds (cuenta paper, fee config, estrategias, risk profiles)
- Variable opcional: `API_BASE_URL` (por defecto `http://localhost:8000`)

## Ejecutar

```bash
cd backend
python scripts/e2e_paper_bot.py
```

## Escenarios

1. **Trade ganador** – Abrir LONG, cerrar por encima; balance sube.
2. **Trade perdedor** – Cerrar por debajo; balance baja.
3. **Rechazo capital insuficiente** – Cantidad/notional > disponible → 400.
4. **Rechazo señal duplicada** – Mismo `idempotency_key` n8n → 409.
5. **Dashboard summary** – Responde con account y open_positions_count.

TP/SL automáticos se comprueban con el supervisor en marcha (backend corriendo).
