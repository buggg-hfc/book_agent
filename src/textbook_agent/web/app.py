"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .job_manager import JobManager
from .routers import files, logs, pipeline, projects


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from ..config import settings
    # Resolve output_dir to an absolute path once at startup so that all
    # request handlers use a stable path regardless of any CWD changes.
    settings.output_dir = str(Path(settings.output_dir).resolve())
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)

    app.state.job_manager = JobManager()
    # Prune stale jobs every 10 minutes.
    async def _prune_loop():
        while True:
            await asyncio.sleep(600)
            app.state.job_manager.prune()
    task = asyncio.create_task(_prune_loop())
    yield
    task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="textbook-agent GUI",
        description="Web interface for the textbook-agent pipeline",
        version="1.0.0",
        lifespan=_lifespan,
    )

    # Allow the Vite dev server (if any) and localhost variants during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router)
    app.include_router(pipeline.router)
    app.include_router(files.router)
    app.include_router(logs.router)

    # Serve the SPA. Mount last so API routes take precedence.
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
