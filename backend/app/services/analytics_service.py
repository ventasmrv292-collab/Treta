"""
Servicio de analytics: resumen, por estrategia, por leverage, curva de equity.
Por ahora delega en las rutas de analytics (DB directo). Opcional: cache en memoria.
"""
from __future__ import annotations

# Los endpoints de analytics ya implementan la lógica en app.api.routes.analytics.
# Este módulo queda para futura caché o agregación server-side.
# Uso: from app.services.analytics_service import ... si se añade cache.
__all__: list[str] = []
