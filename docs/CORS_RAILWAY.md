# CORS: que la web en Vercel pueda llamar al API en Railway

Los errores **"blocked by CORS policy"** aparecen cuando el backend (Railway) no permite peticiones desde el origen de tu frontend (Vercel).

---

## Qué se ha cambiado en el backend

El backend ahora acepta **cualquier dominio `*.vercel.app`** (por defecto), así que tu URL de Vercel (por ejemplo `https://treta-jmljynibf-miguels-projects-898f2199.vercel.app`) debería ser aceptada sin tocar nada más.

Si aun así falla, en **Railway** revisa que no tengas una variable que desactive esto.

---

## Variables en Railway (opcional)

En tu proyecto de Railway → **Variables**:

| Variable | Valor | Comentario |
|----------|--------|------------|
| `CORS_ORIGINS` | `https://tu-dominio.vercel.app` | Opcional. Si quieres restringir a una URL concreta, ponla aquí (varias separadas por coma). |
| `CORS_ALLOW_VERCEL_APP` | `true` | Por defecto ya es `true`. Si lo pones a `false`, solo se permiten los orígenes de `CORS_ORIGINS`. |

No hace falta definir nada si te vale permitir todos los `*.vercel.app`.

---

## Después de cambiar el backend

1. **Sube el cambio** (commit + push del backend).
2. **Railway** volverá a desplegar solo si el repo está conectado; si no, despliega a mano.
3. **Prueba de nuevo** la web en Vercel: recarga (F5) y revisa la consola (F12). Los errores de CORS deberían desaparecer.

Si tu frontend usa **Supabase** para trades/dashboard/analíticas, esas peticiones van a Supabase y no a Railway; los CORS que ves son solo para las llamadas que siguen yendo al API de Railway (por ejemplo precio, klines, supervisor).
