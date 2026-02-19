"""System log service — records activity to the system_logs table."""

from __future__ import annotations

import json

import structlog

from ..storage.database import get_session
from ..storage.repositories import SystemLogRepository

log = structlog.get_logger()

_insert_counter = 0
_TRIM_INTERVAL = 50


async def system_log(
    level: str,
    component: str,
    message: str,
    details: dict | None = None,
) -> None:
    """Insert a system log entry. Trims table every N inserts."""
    global _insert_counter

    details_json = json.dumps(details) if details else None
    try:
        async with get_session() as session:
            repo = SystemLogRepository(session)
            await repo.create(
                level=level,
                component=component,
                message=message,
                details=details_json,
            )
    except Exception as e:
        log.warning("Failed to write system log", error=str(e))
