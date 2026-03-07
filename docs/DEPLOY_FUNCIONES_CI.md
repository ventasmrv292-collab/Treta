# Desplegar Edge Functions desde GitHub (sin usar tu PC)

Las Edge Functions viven en **Supabase**, no en Vercel. Para que el código del repo se suba a Supabase puedes hacerlo:

- **A mano** desde tu PC: `supabase functions deploy ...`
- **Automático** desde GitHub: cada vez que hagas push (o cuando quieras, a mano) un workflow despliega las funciones.

---

## Cómo activar el deploy automático

### 1. Subir el repo a GitHub

Si aún no está:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### 2. Crear los secrets en GitHub

1. Repo → **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret** y crea estos tres:

| Nombre | Dónde sacarlo |
|--------|----------------|
| `SUPABASE_ACCESS_TOKEN` | [Supabase → Account → Access Tokens](https://supabase.com/dashboard/account/tokens). "Generate new token". |
| `SUPABASE_PROJECT_REF` | Supabase → Tu proyecto → **Project Settings** → **General** → **Reference ID** (ej. `abcdefghijklmnop`). |
| `SUPABASE_DB_PASSWORD` | Supabase → **Project Settings** → **Database** → **Database password** (la que pusiste al crear el proyecto). |

### 3. Qué hace el workflow

- Archivo: `.github/workflows/deploy-supabase-functions.yml`
- Se ejecuta:
  - En cada **push a `main`** si cambia algo en `supabase/functions/**`.
  - O cuando tú quieras: pestaña **Actions** → "Deploy Supabase Edge Functions" → **Run workflow**.

Cuando corre, instala la CLI de Supabase, enlaza tu proyecto y ejecuta `supabase functions deploy` para las seis funciones. Así se despliegan **en Supabase**, no en tu PC.

### 4. Ver que funcionó

- GitHub: **Actions** → el último run en verde.
- Supabase: **Edge Functions** → deberías ver la lista de funciones desplegadas.

---

## Resumen

| Dónde corre | Qué es |
|-------------|--------|
| **Vercel** | Tu web (frontend React). Se despliega al hacer push si tienes Vercel conectado al repo. |
| **Supabase** | Base de datos + Edge Functions. Las funciones se despliegan con la CLI (desde tu PC o desde GitHub Actions). |

No hace falta tener la web “en tu PC”: la web está en Vercel y las funciones en Supabase. Solo hace falta que el código de las funciones llegue a Supabase una vez (a mano con la CLI o automático con el workflow).
