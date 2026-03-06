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

## 4. Probar

- **Raíz**: https://treta-ruby.vercel.app → debe redirigir a `/dashboard`.
- **Dashboard**: https://treta-ruby.vercel.app/dashboard → debe cargar sin 404.

Si el backend (FastAPI) está en otro sitio, en el frontend tendrás que usar la URL de esa API (variable de entorno o config) para que las llamadas a `/api` apunten al servidor correcto.
