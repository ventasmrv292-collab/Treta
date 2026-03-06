# API Endpoints

Base URL: `http://localhost:8000/api/v1`

## Market
- `GET /market/price?symbol=BTCUSDT` — Precio actual
- `GET /market/klines?symbol=BTCUSDT&interval=15m&limit=300` — Velas para gráfico

## Trades
- `GET /trades` — Listar operaciones (query: page, size, symbol, strategy_family, strategy_name, source, position_side, leverage, closed_only, winners_only, losers_only, date_from, date_to)
- `GET /trades/{id}` — Obtener una operación
- `POST /trades` — Crear operación manual (body: ManualTradeCreate)
- `PATCH /trades/{id}/close` — Cerrar operación (body: exit_price, exit_order_type, maker_taker_exit, exit_reason, closed_at?)

## Strategies
- `GET /strategies` — Listar estrategias activas
- `GET /strategies/{id}` — Obtener estrategia

## Fee config
- `GET /fee-config` — Listar perfiles de comisiones
- `GET /fee-config/default` — Perfil por defecto
- `GET /fee-config/{id}` — Obtener perfil
- `PATCH /fee-config/{id}` — Actualizar perfil

## Webhook n8n
- `POST /webhook/n8n/trade` — Recibir operación desde n8n (body: N8nTradeCreate)

## Analytics
- `GET /analytics/dashboard` — Métricas del dashboard
- `GET /analytics/by-strategy` — Comparativa por estrategia
- `GET /analytics/by-leverage` — Comparativa por leverage
- `GET /analytics/equity-curve?period=all` — Curva de equity (period: day, week, month, all)

## Backtest
- `POST /backtest` — Ejecutar backtest (body: BacktestRunCreate)
- `GET /backtest` — Listar backtests
- `GET /backtest/{id}` — Detalle de un backtest
