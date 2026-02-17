"""System status and configuration API endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .. import __version__
from ..core.queue import TaskQueue
from ..services.stats import StatsService
from ..storage.database import get_session

router = APIRouter()

_start_time = time.time()


class QueueStats(BaseModel):
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    waiting_llm: int = 0


class StorageStats(BaseModel):
    total_documents: int
    total_chunks: int
    sqlite_size_mb: float


class StatusResponse(BaseModel):
    version: str
    uptime_seconds: int
    queue: QueueStats
    storage: StorageStats
    watched_directories: list[str]


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request):
    """System health and status."""
    config = request.app.state.config

    async with get_session() as session:
        service = StatsService(session, config)
        stats = await service.get_library_stats()

    return StatusResponse(
        version=__version__,
        uptime_seconds=int(time.time() - _start_time),
        queue=QueueStats(
            pending=stats["queue_stats"].get("pending", 0),
            running=stats["queue_stats"].get("running", 0),
            completed=stats["queue_stats"].get("completed", 0),
            failed=stats["queue_stats"].get("failed", 0),
            waiting_llm=stats["queue_stats"].get("waiting_llm", 0),
        ),
        storage=StorageStats(
            total_documents=stats["doc_stats"]["total"],
            total_chunks=stats["total_chunks"],
            sqlite_size_mb=stats["sqlite_size_mb"],
        ),
        watched_directories=config.watch.directories,
    )


@router.get("/queue")
async def get_queue():
    """Task queue overview."""
    async with get_session() as session:
        queue = TaskQueue(session)
        stats = await queue.get_stats()
        return {"queue": stats}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, request: Request = None):
    """WebSocket endpoint for real-time events."""
    events = websocket.app.state.events
    await events.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            # Could handle client-sent events here
    except WebSocketDisconnect:
        events.disconnect(websocket)
