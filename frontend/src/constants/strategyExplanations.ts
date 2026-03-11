/**
 * Explicación sencilla de cada estrategia que usa el bot.
 * Se muestra en la página "Cómo funciona" / Ayuda.
 */
export const STRATEGY_EXPLANATIONS = [
  {
    id: 'breakout_volume_v1',
    family: 'BREAKOUT',
    name: 'breakout_volume_v1',
    version: '1.0.0',
    title: 'Breakout por volumen',
    short: 'Abre LONG cuando el precio cierra por encima de un máximo reciente y el volumen es alto.',
    howItWorks:
      'La estrategia mira las últimas velas (por ejemplo 10–20). Si el cierre de la vela actual supera el máximo de ese periodo y el volumen de la vela es mayor que la media reciente de volumen, considera que hay un “breakout” alcista y genera una señal LONG. Define take profit y stop loss a partir de la distancia típica del precio (ATR). Solo opera en 1m, 5m o 15m según el job que esté corriendo.',
    isV2: false,
  },
  {
    id: 'breakout_volume_v2',
    family: 'BREAKOUT',
    name: 'breakout_volume_v2',
    version: '2.0.0',
    title: 'Breakout por volumen (v2)',
    short: 'Igual concepto que v1 con stop más amplio (ATR 1,2%), lookback 14 y volumen 1,4x. Solo LONG, activa en 15m.',
    howItWorks:
      'La estrategia v2 usa un lookback de 14 velas y exige que el cierre supere el máximo de ese periodo con volumen al menos 1,4 veces la media reciente. El stop loss se calcula con ATR al 1,2% (más amplio que v1) para reducir salidas por ruido. El take profit se ajusta para respetar un ratio riesgo/recompensa mínimo (p. ej. 1,2:1). Solo opera LONG y por defecto está activa en 15m.',
    isV2: true,
  },
  {
    id: 'vwap_snapback_v1',
    family: 'MEAN_REVERSION',
    name: 'vwap_snapback_v1',
    version: '1.0.0',
    title: 'Snapback a la media (VWAP)',
    short: 'Aprovecha cuando el precio se aleja de la media y “vuelve” hacia ella.',
    howItWorks:
      'Calcula una media móvil del precio (actúa como referencia tipo VWAP). Si el precio se desvía de esa media por encima de un porcentaje mínimo (por ejemplo 0,3%), la estrategia asume que puede volver: si está por debajo de la media genera señal LONG (subida hacia la media), si está por encima genera señal SHORT (bajada hacia la media). El take profit suele ser la propia media y el stop loss a mitad de camino entre precio y media.',
    isV2: false,
  },
  {
    id: 'vwap_snapback_v2',
    family: 'MEAN_REVERSION',
    name: 'vwap_snapback_v2',
    version: '2.0.0',
    title: 'Snapback a la media (VWAP) (v2)',
    short: 'Desviación 0,4%, factor de stop 0,6. Solo LONG en 5m y 15m, con validación de R:R.',
    howItWorks:
      'Calcula la media móvil del precio (proxy VWAP). Si el precio se desvía por debajo de la media al menos un 0,4%, genera señal LONG (vuelta hacia la media). El stop se coloca con factor 0,6 respecto a la distancia precio–media. El take profit asegura un ratio riesgo/recompensa mínimo. Solo opera LONG; activa en 5m y 15m con cooldown de 5 minutos.',
    isV2: true,
  },
  {
    id: 'ema_pullback_v1',
    family: 'TREND_PULLBACK',
    name: 'ema_pullback_v1',
    version: '1.0.0',
    title: 'Pullback a la EMA en tendencia',
    short: 'Entra cuando el precio en tendencia hace un retroceso a la EMA y rebota.',
    howItWorks:
      'Calcula una EMA (por ejemplo 20 periodos). Si la EMA está subiendo (tendencia alcista) y el precio se acerca a la EMA desde arriba y la toca o se acerca mucho, genera señal LONG (pullback en alcista). Si la EMA está bajando y el precio se acerca a la EMA desde abajo, genera señal SHORT. Take profit y stop loss se ponen según la distancia a la EMA. Solo entra cuando hay “toque” o proximidad a la EMA dentro de un pequeño porcentaje.',
    isV2: false,
  },
  {
    id: 'ema_pullback_v2',
    family: 'TREND_PULLBACK',
    name: 'ema_pullback_v2',
    version: '2.0.0',
    title: 'Pullback a la EMA (v2)',
    short: 'Toque/proximidad 0,2%, distancias mínimas a EMA y al stop. Por defecto pausada hasta validar.',
    howItWorks:
      'Calcula la EMA del cierre. En tendencia alcista, si el precio se acerca a la EMA desde arriba (toque o proximidad del 0,2%) genera señal LONG; en tendencia bajista, proximidad desde abajo genera SHORT. La v2 exige una distancia mínima a la EMA y al stop (0,25%) para evitar entradas con stop demasiado corto. Take profit con ratio R:R mínimo. Por defecto está pausada hasta validar en backtest/paper.',
    isV2: true,
  },
] as const
