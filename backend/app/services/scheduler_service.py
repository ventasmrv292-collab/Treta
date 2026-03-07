"""
Scheduler interno: ejecuta jobs en segundo plano con intervalos fijos.
Protección contra solapamiento y estado visible vía get_scheduler_status().
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_SCHEDULER,
    EVENT_SCHEDULER_STARTED,
    EVENT_SCHEDULER_ERROR,
)
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

# Estado global para el endpoint de status
_job_last_run: dict[str, float] = {}
_job_last_error: dict[str, str] = {}
_job_locks: dict[str, asyncio.Lock] = {}
_scheduler_started_at: float | None = None


def get_scheduler_status() -> dict[str, Any]:
    """Estado del scheduler para la API (última ejecución por job, errores)."""
    return {
        "running": True,
        "started_at": _scheduler_started_at,
        "jobs": {
            name: {
                "last_run_at": _job_last_run.get(name),
                "last_error": _job_last_error.get(name),
            }
            for name in _job_last_run
        },
    }


async def _run_job(name: str, coro: Callable[[], Awaitable[None]]) -> None:
    """Ejecuta un job con lock para evitar solapamiento."""
    lock = _job_locks.setdefault(name, asyncio.Lock())
    async with lock:
        try:
            await coro()
            _job_last_run[name] = time.time()
            _job_last_error.pop(name, None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            err_msg = str(e)
            _job_last_error[name] = err_msg
            logger.exception("scheduler job %s failed: %s", name, e)
            async with async_session_maker() as session:
                await bot_log_event(
                    session,
                    "ERROR",
                    MODULE_SCHEDULER,
                    EVENT_SCHEDULER_ERROR,
                    f"Job {name}: {err_msg}",
                    context={"job": name, "error": err_msg},
                )
                await session.commit()


async def _loop_job(
    name: str,
    interval_seconds: float,
    coro: Callable[[], Awaitable[None]],
    stagger: float = 0,
) -> None:
    """Bucle infinito que ejecuta el job cada interval_seconds."""
    if stagger > 0:
        await asyncio.sleep(stagger)
    while True:
        await _run_job(name, coro)
        await asyncio.sleep(interval_seconds)


def start_scheduler() -> asyncio.Task[None]:
    """
    Arranca el scheduler: lanza todas las tareas en segundo plano.
    Devuelve una Task que agrupa las tareas (para cancelar en shutdown).
    """
    global _scheduler_started_at
    _scheduler_started_at = time.time()

    from app.services.scheduler_jobs import (
        run_sync_candles_1m,
        run_sync_candles_5m,
        run_sync_candles_15m,
        run_strategies_1m,
        run_strategies_5m,
        run_strategies_15m,
        run_position_supervisor_cycle,
        run_refresh_analytics_cache,
    )

    async def _log_start():
        async with async_session_maker() as session:
            await bot_log_event(
                session,
                "INFO",
                MODULE_SCHEDULER,
                EVENT_SCHEDULER_STARTED,
                "Scheduler iniciado (sync velas, estrategias, supervisor, analytics)",
                context={"started_at": _scheduler_started_at},
            )
            await session.commit()

    async def _bootstrap():
        await _log_start()

    # Intervalos
    # Supervisor cada 15 s
    # Sync 1m cada 60 s, strategies 1m cada 60 s (con pequeño delay tras sync)
    # Sync 5m cada 300 s, strategies 5m cada 300 s
    # Sync 15m cada 900 s, strategies 15m cada 900 s
    # Analytics cache cada 300 s (opcional)

    tasks: list[asyncio.Task[None]] = []

    tasks.append(asyncio.create_task(_loop_job("position_supervisor", 15.0, run_position_supervisor_cycle)))
    tasks.append(asyncio.create_task(_loop_job("sync_candles_1m", 60.0, run_sync_candles_1m)))
    tasks.append(asyncio.create_task(_loop_job("run_strategies_1m", 60.0, run_strategies_1m, stagger=10.0)))
    tasks.append(asyncio.create_task(_loop_job("sync_candles_5m", 300.0, run_sync_candles_5m, stagger=5.0)))
    tasks.append(asyncio.create_task(_loop_job("run_strategies_5m", 300.0, run_strategies_5m, stagger=15.0)))
    tasks.append(asyncio.create_task(_loop_job("sync_candles_15m", 900.0, run_sync_candles_15m, stagger=20.0)))
    tasks.append(asyncio.create_task(_loop_job("run_strategies_15m", 900.0, run_strategies_15m, stagger=30.0)))
    tasks.append(asyncio.create_task(_loop_job("refresh_analytics_cache", 300.0, run_refresh_analytics_cache, stagger=60.0)))

    async def _run_all():
        await _bootstrap()
        await asyncio.gather(*tasks)

    return asyncio.create_task(_run_all())
