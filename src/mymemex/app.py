"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .config import AppConfig, load_config
from .core.events import EventManager
from .core.queue import TaskQueue, TaskType
from .core.watcher import FileWatcher
from .core.scheduler import embedding_scheduler
from .processing.pipeline import handle_new_file, task_worker
from .storage.database import get_session, init_database
from .storage.repositories import DocumentRepository

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    config: AppConfig = app.state.config
    events: EventManager = app.state.events
    loop = asyncio.get_running_loop()

    # Startup
    log.info("MyMemex starting up", debug=config.debug)

    # Initialize database
    await init_database(config.database.path)

    # Recover stale tasks from previous crashes
    async with get_session() as session:
        queue = TaskQueue(session)
        recovered = await queue.recover_stale()
        if recovered:
            log.info("Recovered stale tasks from previous run", count=recovered)

    # Recover documents stuck in "processing" with no active task
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        queue = TaskQueue(session)
        stuck = await doc_repo.find_stuck_processing()
        for doc in stuck:
            await doc_repo.update_status(doc, "pending")
            await queue.enqueue(
                task_type=TaskType.INGEST,
                payload={"document_id": doc.id, "path": doc.original_path},
                document_id=doc.id,
                priority=8,
            )
        if stuck:
            log.info("Recovered stuck documents", count=len(stuck))

    # Start file watcher (DB-driven directories)
    async def on_new_file(path):
        await handle_new_file(path, config, events)

    watcher = FileWatcher(
        config,
        on_new_file=on_new_file,
        db_path=str(config.database.path),
    )
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

    log.info("MyMemex ready")
    await events.broadcast("system.started", {"version": "0.1.0"})

    # Run MCP session manager for the app lifetime (if HTTP transport is mounted)
    async with AsyncExitStack() as stack:
        mcp_session_manager = getattr(app.state, "mcp_session_manager", None)
        if mcp_session_manager:
            await stack.enter_async_context(mcp_session_manager.run())
            log.info("MCP session manager started")
        yield

    # Shutdown
    log.info("MyMemex shutting down")

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
    log.info("MyMemex stopped")


class SameOriginAdminMiddleware(BaseHTTPMiddleware):
    """Restrict admin API endpoints to same-origin requests."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/admin/"):
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                base_netloc = request.base_url.netloc
                if parsed.netloc != base_netloc:
                    return Response("Forbidden", status_code=403)
        return await call_next(request)


def _configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog to write directly to stdout, bypassing stdlib logging."""
    import logging as _logging
    level = getattr(_logging, log_level.upper(), _logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if log_level.upper() == "DEBUG" else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create FastAPI application."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title="MyMemex",
        description="Sovereign document intelligence platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    _configure_logging(config.log_level)

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

    # Same-origin restriction for admin endpoints
    app.add_middleware(SameOriginAdminMiddleware)

    # Demo mode restriction
    from .middleware.demo_mode import DemoModeMiddleware
    app.add_middleware(DemoModeMiddleware)

    # Auth enforcement (runs first — innermost middleware)
    from .middleware.auth import AuthMiddleware
    app.add_middleware(AuthMiddleware)

    # Include API router
    from .api.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    # Include Web UI router + static files
    from .web.router import router as web_router

    app.include_router(web_router, prefix="/ui")
    app.mount(
        "/ui/static",
        StaticFiles(directory=str(Path(__file__).parent / "web" / "static")),
        name="static",
    )

    # MCP HTTP transport — mount at /mcp when configured
    import os

    if config.mcp.enabled and os.environ.get("DEMO_MODE") != "true":
        try:
            from .mcp import create_mcp_server
            from .middleware.mcp_auth import MCPAuthMiddleware

            mcp_server = create_mcp_server(config)
            mcp_http_app = mcp_server.streamable_http_app()
            # Store session manager so lifespan can start it
            app.state.mcp_session_manager = mcp_server.session_manager
            if config.mcp.auth.mode != "none":
                mcp_http_app = MCPAuthMiddleware(mcp_http_app, config)
            app.mount("/mcp", mcp_http_app)
            log.info("MCP HTTP transport mounted", path="/mcp")
        except Exception as e:
            log.warning("MCP HTTP transport not mounted", error=str(e))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
