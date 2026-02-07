"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response

from pytoon.api_orchestrator.routes import health_router, router
from pytoon.config import get_settings
from pytoon.db import init_db
from pytoon.log import setup_logging, get_logger
from pytoon.metrics import metrics_text

logger = get_logger(__name__)

# Flag: set True when running in combined mode (API + worker in one process)
_embedded_worker: bool = False
_worker_thread: threading.Thread | None = None


def enable_embedded_worker():
    """Call before create_app() to run the worker inside the API process."""
    global _embedded_worker
    _embedded_worker = True


def _run_worker_in_thread():
    """Run the worker loop in its own thread with its own event loop.

    This prevents blocking ffmpeg/subprocess calls from starving the
    FastAPI event loop.
    """
    from pytoon.worker.main import worker_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(worker_loop())
    except Exception as exc:
        logger.error("embedded_worker_crashed", error=str(exc))
    finally:
        loop.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global _worker_thread
    setup_logging(json_output=False)  # console-friendly for local dev
    init_db()
    logger.info("api_started", port=get_settings().api_port)

    if _embedded_worker:
        _worker_thread = threading.Thread(
            target=_run_worker_in_thread,
            daemon=True,
            name="pytoon-worker",
        )
        _worker_thread.start()
        logger.info("embedded_worker_started")

    yield

    if _worker_thread is not None:
        from pytoon.worker.main import _shutdown as _ws
        import pytoon.worker.main as wm
        wm._shutdown = True
        _worker_thread.join(timeout=5)
        logger.info("embedded_worker_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pytoon Render Engine",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(router)

    @app.get("/metrics")
    async def prom_metrics():
        return Response(content=metrics_text(), media_type="text/plain")

    return app


app = create_app()
