# Esquema de base de datos (PostgreSQL)

## Tablas

### strategies
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| family | VARCHAR(64) | Familia (BREAKOUT, MEAN_REVERSION, TREND_PULLBACK) |
| name | VARCHAR(128) | Nombre (breakout_volume_v1, etc.) |
| version | VARCHAR(32) | Versión |
| description | TEXT | Descripción opcional |
| default_params_json | TEXT | Parámetros por defecto JSON |
| active | BOOLEAN | Activa |
| created_at, updated_at | TIMESTAMPTZ | Auditoría |

### fee_configs
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| name | VARCHAR(64) | conservative, realistic, optimistic |
| maker_fee_bps | NUMERIC(10,4) | Comisión maker en basis points |
| taker_fee_bps | NUMERIC(10,4) | Comisión taker |
| bnb_discount_pct | NUMERIC(5,2) | Descuento BNB % |
| default_slippage_bps | NUMERIC(10,2) | Slippage por defecto |
| include_funding | BOOLEAN | Incluir funding |
| is_default | BOOLEAN | Perfil por defecto |
| created_at, updated_at | TIMESTAMPTZ | Auditoría |

### trades
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| source | VARCHAR(32) | manual, n8n |
| symbol, market | VARCHAR | BTCUSDT, usdt_m |
| strategy_family, strategy_name, strategy_version | VARCHAR | Estrategia |
| strategy_id | FK → strategies.id | Opcional |
| timeframe | VARCHAR(16) | 1m, 5m, 15m, 1h |
| position_side | VARCHAR(8) | LONG, SHORT |
| order_side_entry | VARCHAR(8) | BUY, SELL |
| order_type_entry | VARCHAR(16) | MARKET, LIMIT |
| maker_taker_entry | VARCHAR(8) | MAKER, TAKER |
| leverage | INT | 10, 20, ... |
| quantity | NUMERIC(20,8) | Cantidad |
| entry_price | NUMERIC(20,8) | Precio entrada |
| take_profit, stop_loss | NUMERIC | Opcionales |
| signal_timestamp | TIMESTAMPTZ | Para n8n |
| strategy_params_json, notes | TEXT | Opcionales |
| exit_price, exit_order_type, maker_taker_exit | Varios | Cierre |
| exit_reason | VARCHAR(64) | take_profit, stop_loss, etc. |
| closed_at | TIMESTAMPTZ | Fecha cierre |
| entry_notional, exit_notional | NUMERIC | Calculados |
| entry_fee, exit_fee, funding_fee, slippage_usdt | NUMERIC | Fees |
| gross_pnl_usdt, net_pnl_usdt | NUMERIC | PnL |
| pnl_pct_notional, pnl_pct_margin | NUMERIC | Porcentajes |
| created_at, updated_at | TIMESTAMPTZ | Auditoría |

### candles
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| symbol, interval | VARCHAR | BTCUSDT, 15m |
| open_time | TIMESTAMPTZ | Apertura vela |
| open, high, low, close, volume | NUMERIC | OHLCV |
| created_at | TIMESTAMPTZ | Auditoría |

### backtest_runs
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| strategy_* | VARCHAR | Estrategia |
| symbol, interval | VARCHAR | Mercado y TF |
| start_time, end_time | TIMESTAMPTZ | Rango |
| initial_capital | NUMERIC | Capital |
| leverage | INT | Apalancamiento |
| fee_profile, slippage_bps | VARCHAR/NUMERIC | Config |
| status | VARCHAR | pending, running, completed, failed |
| total_trades, net_pnl, gross_pnl, total_fees | Varios | Resultados |
| win_rate, profit_factor, max_drawdown_pct | Varios | Métricas |
| created_at | TIMESTAMPTZ | Auditoría |

### backtest_results
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL | PK |
| run_id | FK → backtest_runs.id | Backtest |
| trade_index | INT | Índice del trade |
| entry_time, exit_time | TIMESTAMPTZ | Horarios |
| position_side | VARCHAR | LONG, SHORT |
| entry_price, exit_price | NUMERIC | Precios |
| quantity | NUMERIC | Cantidad |
| gross_pnl, fees, net_pnl | NUMERIC | PnL y fees |
| exit_reason | VARCHAR | Motivo cierre |
