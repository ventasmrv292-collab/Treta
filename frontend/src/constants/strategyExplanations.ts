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
  },
] as const
