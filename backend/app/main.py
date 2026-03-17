"""FastAPI application entry point."""
import asyncio
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_db
from app.api.routes import api_router
from app.services.price_stream import run_price_stream

# Regex para permitir origen Vercel en respuestas de error (cuando el middleware no añade CORS).
VERCEL_ORIGIN_REGEX = re.compile(r"^https://[a-z0-9-]+\.vercel\.app$")

# Si el refactor (scheduler_service) no está desplegado, arrancar solo price stream + supervisor como antes.
try:
    from app.services.scheduler_service import start_scheduler
    _use_scheduler = True
except ImportError:
    _use_scheduler = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task_stream = asyncio.create_task(run_price_stream())
    if _use_scheduler:
        task_scheduler = start_scheduler()
    else:
        from app.services.position_supervisor import run_position_supervisor
        task_scheduler = asyncio.create_task(run_position_supervisor())
    yield
    task_stream.cancel()
    task_scheduler.cancel()
    try:
        await task_stream
    except asyncio.CancelledError:
        pass
    try:
        await task_scheduler
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Crypto Futures Sim API",
    description="API para simulación y análisis de operaciones de futuros cripto (paper trading)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_vercel_regex if settings.cors_allow_vercel_app else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Devuelve 500 con cabeceras CORS para que el front en Vercel no vea bloqueo CORS."""
    origin = request.headers.get("origin") or ""
    headers = {}
    if origin and (
        origin in settings.cors_origins_list
        or (settings.cors_allow_vercel_app and VERCEL_ORIGIN_REGEX.match(origin))
    ):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers=headers,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
