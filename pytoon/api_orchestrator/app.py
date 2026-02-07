"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response

from pytoon.api_orchestrator.routes import health_router, router
from pytoon.config import get_settings
from pytoon.db import init_db
from pytoon.log import setup_logging
from pytoon.metrics import metrics_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    setup_logging(json_output=True)
    init_db()
    yield


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
