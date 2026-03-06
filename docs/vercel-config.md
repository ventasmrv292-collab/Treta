# Configuración en Vercel

Para que la app funcione en **https://treta-ruby.vercel.app** (y que `/dashboard`, `/history`, etc. no den 404), configura lo siguiente.

## 1. Root Directory

El repo es un **monorepo** (carpetas `frontend` y `backend`). Vercel debe construir solo el frontend.

1. Entra en tu proyecto en Vercel: **treta-ruby**.
2. **Settings** → **General**.
3. En **Root Directory** haz clic en **Edit**.
4. Escribe: **`frontend`**.
5. Guarda (**Save**).

Así Vercel usará la carpeta `frontend` como raíz del proyecto y aplicará el `vercel.json` que contiene los rewrites para la SPA.

## 2. Build (comprobar)

Con Root Directory = `frontend`, no suele hace falta tocar nada más:

- **Framework Preset**: Vite (se detecta solo).
- **Build Command**: `npm run build`.
- **Output Directory**: `dist`.
- **Install Command**: `npm install`.

Si algo falla al construir, revisa la pestaña **Deployments** → último deployment → **Building** para ver el error.

## 3. Redeploy

Después de cambiar el Root Directory:

1. **Deployments** → los tres puntos del último deployment → **Redeploy**.
2. O haz un nuevo **push** al repo.

## 4. Variable de entorno: URL del backend (para que carguen los datos)

El frontend en Vercel **no tiene backend**: las llamadas a `/api/v1` irían al mismo dominio y fallan. Hay que indicar la URL de tu API:

1. **Despliega el backend** en algún servicio (Render, Fly.io, Railway, etc.) y anota la URL (ej: `https://crypto-sim-api.onrender.com`).
2. En Vercel: **Settings** → **Environment Variables**.
3. Añade:
   - **Name:** `VITE_API_BASE_URL`
   - **Value:** la URL del backend **sin barra final** (ej: `https://crypto-sim-api.onrender.com`).
4. **Redeploy** el frontend (las variables `VITE_*` se embeben en el build).

En el backend, en **CORS**, añade tu dominio de Vercel (ej: `https://treta-ruby.vercel.app`) en `CORS_ORIGINS` para que el navegador permita las peticiones.

## 5. Probar

- **Raíz**: https://treta-ruby.vercel.app → debe redirigir a `/dashboard`.
- **Dashboard**: https://treta-ruby.vercel.app/dashboard → debe cargar y mostrar precio, gráfico y métricas si el backend está configurado y accesible.
