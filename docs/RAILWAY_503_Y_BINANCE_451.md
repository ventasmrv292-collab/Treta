# 503 en el frontend y Binance 451 en el backend

## Qué está pasando

1. **Frontend**: Las peticiones a `https://tu-app.up.railway.app/api/v1/market/price` o `/market/klines` devuelven **503 (Service Unavailable)**.
2. **Backend (logs)**: Aparece **"Binance no disponible: Client error '451'"**. El 451 significa "Unavailable For Legal Reasons": Binance bloquea el acceso desde la región/IP donde está desplegado Railway.

## Por qué 503

- **503 desde nuestra API**: Solo lo devolvemos en `/market/price` y `/market/klines` cuando hay **límite de peticiones (429)** del proveedor de datos, con cabecera `Retry-After`. Si ves 503, puede ser rate limit (CoinGecko/Binance).
- **503 desde Railway**: Si el servicio está arrancando, sobrecargado o se reinicia, Railway puede devolver 503. En ese caso el problema es la disponibilidad del servicio, no solo mercado.

## Cambios hechos para que no falle en cascada

1. **Sync de velas**: Si Binance devuelve 451, el job de sync **ya no lanza excepción**. Se registra `CANDLES_SYNC_ERROR` en los logs del bot y el job termina sin insertar velas. El scheduler sigue estable y no llena los logs de errores.
2. **Precio y velas para el gráfico**: En entornos donde Railway inyecta `PORT`, el backend usa **CoinGecko** para precio y klines (no llama a Binance). Así el gráfico y el precio pueden seguir funcionando aunque Binance esté bloqueado.

## Qué comprobar

1. **Variable de entorno en Railway**  
   - Si quieres forzar Binance cuando esté disponible: `USE_BINANCE_FOR_MARKET=1`.  
   - Si Binance da 451 en tu región: **no** pongas esa variable (o pon `USE_COINGECKO_FOR_MARKET=1`). Así el backend usará CoinGecko para precio y gráfico.

2. **Que el frontend apunte al backend**  
   - En Vercel (o donde tengas el frontend), `VITE_API_BASE_URL` debe ser la URL de tu app en Railway (ej. `https://treta-production.up.railway.app`), sin barra final.

3. **Si sigues viendo 503**  
   - Revisa en Railway que el servicio esté en estado "Running" y que no se reinicie por fallos.  
   - Prueba en el navegador: `https://tu-app.up.railway.app/health` → debe devolver `{"status":"ok"}`.  
   - Si `/health` responde bien pero `/api/v1/market/price` da 503, entonces es rate limit (429) del proveedor; espera 1–2 minutos y reintenta.

4. **Velas en Supabase con volumen 0**  
   - Si Binance devuelve 451, el sync no puede obtener velas con volumen. Las filas que ves con volumen 0 son de una ingesta anterior o de otro origen. Para tener volumen real, el backend tiene que poder llamar a Binance (por ejemplo en otra región o desde una VPN permitida).
