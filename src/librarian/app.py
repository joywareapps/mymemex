"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig, load_config
from .core.events import EventManager
from .core.queue import TaskQueue
from .core.watcher import FileWatcher
from .core.scheduler import embedding_scheduler
from .processing.pipeline import handle_new_file, task_worker
from .storage.database import get_session, init_database

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    config: AppConfig = app.state.config
    events: EventManager = app.state.events
    loop = asyncio.get_running_loop()

    # Startup
    log.info("Librarian starting up", debug=config.debug)

    # Initialize database
    await init_database(config.database.path)

    # Recover stale tasks from previous crashes
    async with get_session() as session:
        queue = TaskQueue(session)
        recovered = await queue.recover_stale()
        if recovered:
            log.info("Recovered stale tasks from previous run", count=recovered)

    # Start file watcher
    async def on_new_file(path):
        await handle_new_file(path, config, events)

    watcher = FileWatcher(config, on_new_file=on_new_file)
    watcher.start(loop=loop)
    app.state.watcher = watcher

    # Start task workers
    workers = []
    for i in range(2):
        worker = asyncio.create_task(task_worker(config, events=events, worker_id=i))
        workers.append(worker)
    app.state.workers = workers

    # Start embedding scheduler (if AI enabled)
    scheduler_task = None
    if config.ai.semantic_search_enabled:
        scheduler_task = asyncio.create_task(embedding_scheduler(config))
        app.state.scheduler_task = scheduler_task
        log.info("Embedding scheduler started")

    log.info("Librarian ready", watched_dirs=config.watch.directories)
    await events.broadcast("system.started", {"version": "0.1.0"})

    yield

    # Shutdown
    log.info("Librarian shutting down")

    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

    for worker in workers:
        worker.cancel()

    for worker in workers:
        try:
            await worker
        except asyncio.CancelledError:
            pass

    watcher.stop()
    log.info("Librarian stopped")


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create FastAPI application."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title="Librarian",
        description="Sovereign document intelligence platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.config = config
    app.state.events = EventManager()

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    from .api.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
