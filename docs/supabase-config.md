# Configuración con Supabase

Proyecto Supabase: **zgnplakatvpmhhczvkzv**

- **URL del proyecto**: `https://zgnplakatvpmhhczvkzv.supabase.co`
- **API REST**: `https://zgnplakatvpmhhczvkzv.supabase.co/rest/v1`

## 1. Backend (FastAPI) – Base de datos

El backend está preparado para tu **Transaction pooler** (URI, puerto 6543, `aws-1-eu-west-1`).

1. En la carpeta **backend**, crea un archivo **`.env`** (no lo subas al repo).
2. Copia el contenido de **`.env.example`** y descomenta la línea de Supabase.
3. Sustituye `[YOUR-PASSWORD]` por la contraseña de la base de datos (Supabase no la muestra; si no la recuerdas, reseteala en **Project Settings → Database**).

Connection string exacta (formato async para Python):

```env
DATABASE_URL=postgresql+asyncpg://postgres.zgnplakatvpmhhczvkzv:[YOUR-PASSWORD]@aws-1-eu-west-1.pooler.supabase.com:6543/postgres
```

El código desactiva automáticamente el caché de prepared statements cuando detecta `pooler.supabase.com`, porque el **Transaction pooler** no soporta `PREPARE`.

## 2. Frontend (opcional) – Anon key

Si más adelante usas el cliente de Supabase en el frontend (realtime, auth, etc.), necesitarás la **anon public** key. **No la subas al repositorio.** Guárdala solo en:

- `.env.local` en el frontend (y añade `.env.local` al `.gitignore`), o
- variables de entorno en tu plataforma de despliegue.

Ejemplo en el frontend (si usas Supabase JS):

```env
VITE_SUPABASE_URL=https://zgnplakatvpmhhczvkzv.supabase.co
VITE_SUPABASE_ANON_KEY=tu_anon_key_aqui
```

## 3. Crear tablas en Supabase

1. En Supabase: **SQL Editor** → **New query**.
2. Pega y ejecuta el contenido de `docs/supabase-schema.sql`.
3. (Opcional) Ejecuta el seed del backend contra esta base para cargar estrategias, fee configs y datos de ejemplo:

```bash
cd backend
# Asegúrate de que .env tiene DATABASE_URL apuntando a Supabase
python scripts/seed.py
```

## 4. Resumen de variables

| Variable        | Dónde      | Descripción |
|----------------|------------|-------------|
| `DATABASE_URL` | Backend .env | URI de PostgreSQL con `postgresql+asyncpg://...` (pooler 6543). |
| Anon key       | Solo local / deploy | Para cliente Supabase en frontend; no poner en el repo. |
