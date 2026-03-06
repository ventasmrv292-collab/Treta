# Desplegar el backend en Render (Web Service)

Así subes el backend FastAPI a Render para que el frontend en Vercel pueda cargar precio, velas y métricas.

## 1. Elegir el tipo de servicio

En la pantalla que tienes abierta:

- Haz clic en **"New Web Service →"** (la opción **Web Services** — "Dynamic web app. Ideal for full-stack apps, **API servers**...").

## 2. Conectar el repositorio

- Si te pide conectar cuenta, elige **GitHub** y autoriza Render.
- Busca y selecciona el repo **ventasmrv292-collab/Treta** (o el nombre real de tu repo).
- Si el repo es de una organización, puede que tengas que dar acceso a Render a esa org.

## 3. Configurar el Web Service

Rellena así (importante el **Root Directory** y el **Start Command**):

| Campo | Valor |
|-------|--------|
| **Name** | `crypto-sim-api` (o el nombre que quieras) |
| **Region** | El más cercano a ti (ej: Frankfurt) |
| **Branch** | `main` |
| **Root Directory** | **`backend`** ← obligatorio (tu código del API está en la carpeta `backend`) |
| **Runtime** | **Python 3** |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python run.py` |

## 4. Variables de entorno (Environment)

En la sección **Environment Variables** añade estas variables (botón **Add Environment Variable**):

| Key | Value |
|-----|--------|
| `DATABASE_URL` | La connection string de **Supabase** (Transaction pooler). Puedes copiarla tal cual desde Supabase (empieza por `postgresql://`); el backend la convierte a `postgresql+asyncpg://`. Ejemplo: `postgresql://postgres.zgnplakatvpmhhczvkzv:TU_PASSWORD@aws-1-eu-west-1.pooler.supabase.com:6543/postgres` **Importante:** si la contraseña tiene caracteres especiales (`@`, `#`, `/`, `%`), codifícala en URL (ej. `@` → `%40`). |
| `CORS_ORIGINS` | `https://treta-ruby.vercel.app` (la URL de tu frontend en Vercel; si tienes más orígenes, sepáralos por coma) |
| `DEBUG` | `false` (opcional; en producción mejor false) |

No hace falta poner `PORT`: Render la inyecta sola y el backend ya la usa.

## 5. Crear el servicio

- Revisa que **Root Directory** sea `backend` y el **Start Command** `python run.py`.
- Pulsa **Create Web Service**.

Render hará el build (`pip install -r requirements.txt`) y luego ejecutará `python run.py`. La primera vez puede tardar unos minutos.

## 6. Obtener la URL del backend

Cuando el deploy termine en estado **Live**:

- Arriba verás la URL del servicio, algo como:  
  **`https://crypto-sim-api.onrender.com`**
- Esa es la URL que debe usar el frontend.

## 7. Configurar el frontend en Vercel

En **Vercel** → tu proyecto del frontend:

1. **Settings** → **Environment Variables**
2. Añade:
   - **Name:** `VITE_API_BASE_URL`
   - **Value:** la URL de Render **sin barra final** (ej: `https://crypto-sim-api.onrender.com`)
3. **Redeploy** el frontend (Deployments → Redeploy).

A partir de ahí, la app en Vercel cargará los datos desde el backend en Render.

## 8. (Opcional) Datos iniciales en Supabase

Si la base en Supabase está vacía (sin estrategias ni operaciones de ejemplo), en tu PC, con el `.env` del backend apuntando a la misma `DATABASE_URL` de Supabase, ejecuta una vez:

```bash
cd backend
python scripts/seed.py
```

Eso crea estrategias, perfiles de fees y trades de ejemplo. No hace falta ejecutarlo en Render.

## Resumen rápido

1. **Render:** New Web Service → repo **Treta** → **Root Directory: `backend`** → Build: `pip install -r requirements.txt` → Start: `python run.py` → Env: `DATABASE_URL`, `CORS_ORIGINS`.
2. **Vercel:** Variable `VITE_API_BASE_URL` = URL del Web Service de Render (sin barra final) → Redeploy.
