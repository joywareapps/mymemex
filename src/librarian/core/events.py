"""WebSocket event manager for real-time UI updates."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import WebSocket

log = structlog.get_logger()


class EventManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        log.debug("WebSocket client connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        log.debug("WebSocket client disconnected", total=len(self._connections))

    async def broadcast(self, event: str, data: dict | None = None):
        """Send event to all connected clients. Remove dead connections."""
        if not self._connections:
            return

        message = {
            "event": event,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)
