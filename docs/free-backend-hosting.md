# Servicios gratuitos para desplegar el backend (y usar Binance)

En **Render** la API de Binance suele devolver **451** (bloqueo por región/IP). En otros proveedores, según la región del servidor, Binance puede funcionar bien.

## Opciones gratuitas a probar

### 1. **Railway** (recomendado para probar primero)
- **Web:** https://railway.app  
- **Ventajas:** Plan gratuito con créditos mensuales, despliegue desde GitHub, servidores en **EE.UU.** (menos bloqueos de Binance), variables de entorno, dominio `.railway.app`.
- **Pasos:** Conectar repo → Root Directory: `backend` → Build: `pip install -e .` (o según tu `pyproject.toml`) → Start: `python run.py` o `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Definir `USE_BINANCE_FOR_MARKET=1` para intentar Binance primero (y no usar CoinGecko por defecto).

### 2. **Fly.io**
- **Web:** https://fly.io  
- **Ventajas:** Plan gratuito, eliges **región** (por ejemplo `iad` Virginia, `lax` Los Ángeles). Útil si quieres probar una región concreta.
- **Regiones que suelen ir bien con Binance:** `iad` (US East), `lax` (US West), `ams` (Ámsterdam). Puedes crear la app con `fly launch` y en `fly.toml` poner `[env] USE_BINANCE_FOR_MARKET = "1"`.

### 3. **Koyeb**
- **Web:** https://www.koyeb.com  
- **Ventajas:** Plan free tier, despliegue desde GitHub, varias regiones (EU, US).
- Probar con región **US** y `USE_BINANCE_FOR_MARKET=1`.

### 4. **Google Cloud Run**
- **Web:** https://cloud.run  
- **Ventajas:** Free tier generoso, contenedores, región elegible (por ejemplo `us-central1`).
- Más pasos de configuración (Docker, cuenta GCP). Útil si ya usas GCP.

### 5. **Oracle Cloud (Always Free)**
- **Web:** https://www.oracle.com/cloud/free  
- **Ventajas:** VPS gratis permanente (AMD), tú eliges región (por ejemplo US).
- Requiere crear una VM, instalar Python y ejecutar el backend tú mismo (más control, más trabajo).

---

## Variables de entorno útiles al cambiar de Render

En el **nuevo servicio** configura al menos:

- `DATABASE_URL` — misma URL de Supabase (o la BD que uses).
- `CORS_ORIGINS` — incluir la URL del frontend, p. ej. `https://treta-ruby.vercel.app`.
- **`USE_BINANCE_FOR_MARKET=1`** — para que el backend intente Binance primero en lugar de CoinGecko.

Si aun así Binance devuelve 451, puedes probar un endpoint alternativo (si tu cliente lo soporta):

- `BINANCE_FUTURES_REST_URL=https://fapi1.binance.com`  
  (en `config.py` ya se usa `binance_futures_rest_url`; asegúrate de que el cliente HTTP use esta base URL).

---

## Resumen

| Servicio   | Facilidad | Región elegible | Probar Binance        |
|-----------|-----------|------------------|------------------------|
| Railway   | Alta      | US (por defecto) | Sí, buen primer intento |
| Fly.io    | Media     | Sí (iad, lax…)   | Sí                     |
| Koyeb     | Alta      | Sí               | Sí                     |
| Cloud Run | Media     | Sí               | Sí                     |
| Oracle    | Baja      | Sí               | Sí (máximo control)    |

Ningún proveedor está “garantizado” por Binance; depende de la IP/región. Lo más práctico es probar **Railway** o **Fly.io** con `USE_BINANCE_FOR_MARKET=1` y, si sigue el 451, probar otra región o otro proveedor.
