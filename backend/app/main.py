"""FastAPI application entry point."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.api.routes import api_router
from app.services.price_stream import run_price_stream
from app.services.tp_sl_checker import run_tp_sl_checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task_stream = asyncio.create_task(run_price_stream())
    task_tp_sl = asyncio.create_task(run_tp_sl_checker())
    yield
    task_stream.cancel()
    task_tp_sl.cancel()
    try:
        await task_stream
    except asyncio.CancelledError:
        pass
    try:
        await task_tp_sl
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
