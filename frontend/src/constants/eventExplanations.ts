/**
 * Explicación de cada tipo de evento del log del bot.
 * Se muestra al hacer clic en el evento en la lista de logs.
 */
export const EVENT_EXPLANATIONS: Record<
  string,
  { title: string; description: string; logic: string }
> = {
  CANDLES_SYNC_OK: {
    title: 'Velas sincronizadas',
    description: 'El backend descargó velas cerradas de Binance y las guardó en la base de datos.',
    logic: 'Cada 1 min (1m), 5 min (5m) y 15 min (15m) el scheduler pide las últimas velas a Binance, filtra solo las que ya cerraron (no la vela en formación) y las inserta o actualiza en la tabla candles. Así las estrategias siempre trabajan con datos ya cerrados.',
  },
  CANDLES_SYNC_ERROR: {
    title: 'Error al sincronizar velas',
    description: 'Falló la descarga o guardado de velas desde Binance.',
    logic: 'Puede deberse a red, límite de Binance o error en la base de datos. El backend lo registrará y reintentará en el siguiente ciclo.',
  },
  STRATEGY_SIGNAL_CREATED: {
    title: 'Señal de estrategia → trade abierto',
    description: 'Una estrategia detectó condiciones de mercado y se abrió una operación automática.',
    logic: 'El motor de estrategias evaluó las velas, la estrategia devolvió una señal (entrada LONG o SHORT con precio, TP y SL). Se validó capital y riesgo, se creó el trade, se actualizó la cuenta y se registró en signal_events y account_ledger.',
  },
  TRADE_OPENED: {
    title: 'Operación abierta',
    description: 'Se abrió una nueva posición (manual o automática).',
    logic: 'Se reservó margen, se descontó la comisión de entrada y se actualizó el balance disponible de la cuenta paper.',
  },
  TRADE_CLOSED: {
    title: 'Operación cerrada',
    description: 'Se cerró una posición (manual o por TP/SL).',
    logic: 'Se calculó PnL bruto y neto, comisiones de salida, se liberó el margen, se aplicó el PnL al balance y se actualizó el ledger.',
  },
  TP_HIT: {
    title: 'Take profit alcanzado',
    description: 'El precio llegó al objetivo de beneficio y la posición se cerró automáticamente.',
    logic: 'El supervisor compara cada 15 s el precio actual con el take_profit del trade. Si precio ≥ TP (LONG) o precio ≤ TP (SHORT), cierra el trade a ese precio y registra el cierre.',
  },
  SL_HIT: {
    title: 'Stop loss alcanzado',
    description: 'El precio tocó el stop loss y la posición se cerró automáticamente para limitar la pérdida.',
    logic: 'El supervisor compara cada 15 s el precio con el stop_loss. Si precio ≤ SL (LONG) o precio ≥ SL (SHORT), cierra el trade a ese precio.',
  },
  SIGNAL_REJECTED: {
    title: 'Señal rechazada',
    description: 'Llegó una señal (del motor o de fuera) pero no se abrió operación.',
    logic: 'Puede ser por falta de capital, margen insuficiente, cuenta no encontrada u otra validación. La señal se guarda en signal_events con status REJECTED y el motivo en decision_reason.',
  },
  DUPLICATE_SIGNAL: {
    title: 'Señal duplicada',
    description: 'Se intentó abrir un trade con una señal ya procesada (mismo idempotency_key).',
    logic: 'Para evitar abrir dos veces la misma operación, cada señal puede llevar una clave única. Si ya existe un trade con esa clave, se rechaza y no se abre otro.',
  },
  RISK_LIMIT_BLOCK: {
    title: 'Bloqueado por riesgo',
    description: 'No se abrió la operación porque se superaría algún límite del perfil de riesgo.',
    logic: 'El perfil de riesgo define máx. posiciones abiertas, % máximo de margen, pérdida diaria en USDT o %, cooldown tras pérdidas consecutivas o leverage permitido. Si abrir este trade incumpliría alguno, se rechaza la señal.',
  },
  SUPERVISOR_ERROR: {
    title: 'Error del supervisor',
    description: 'El proceso que revisa TP/SL y actualiza PnL no realizado falló en un ciclo.',
    logic: 'Cada 15 s el supervisor obtiene el precio, actualiza el PnL no realizado por cuenta y revisa si algún trade debe cerrarse por TP o SL. Si hay error de red o de base de datos, se registra aquí y se reintentará en el siguiente ciclo.',
  },
  SUPERVISOR_PNL_UPDATE: {
    title: 'Actualización de PnL no realizado',
    description: 'Se actualizó el beneficio/pérdida no realizado de las cuentas según el precio actual.',
    logic: 'Para cada cuenta con posiciones abiertas, se calcula (precio actual - precio entrada) × cantidad según el lado (LONG/SHORT) y se guarda en unrealized_pnl_usdt y en available_balance.',
  },
  SUPERVISOR_TICK: {
    title: 'Ciclo del supervisor',
    description: 'El supervisor ejecutó un ciclo (cada 15 segundos).',
    logic: 'En cada ciclo se obtiene el precio de BTCUSDT, se actualiza el PnL no realizado y se comprueba si algún trade debe cerrarse por take profit o stop loss.',
  },
  SCHEDULER_STARTED: {
    title: 'Scheduler iniciado',
    description: 'El planificador de tareas del backend arrancó correctamente.',
    logic: 'Al levantar el backend se inician los jobs: sync de velas (1m, 5m, 15m), ejecución de estrategias (1m, 5m, 15m), supervisor cada 15 s y opcionalmente refresh de analytics. Este evento confirma que todo está en marcha.',
  },
  SCHEDULER_ERROR: {
    title: 'Error en un job del scheduler',
    description: 'Uno de los jobs programados (sync velas, estrategias, supervisor, etc.) falló.',
    logic: 'Cada job tiene su propio manejo de errores; el fallo se registra aquí con el nombre del job y el mensaje. El scheduler sigue ejecutando el resto de jobs y reintentará el siguiente ciclo.',
  },
  SIGNAL_RECEIVED: {
    title: 'Señal recibida',
    description: 'Llegó una señal externa (por ejemplo desde n8n) y se registró.',
    logic: 'Se guarda en signal_events. Después se valida idempotencia, capital y riesgo; si todo es correcto se abre el trade y se enlaza a la señal.',
  },
}

export function getEventExplanation(eventType: string): { title: string; description: string; logic: string } | null {
  return EVENT_EXPLANATIONS[eventType] ?? null
}
