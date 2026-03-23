"""Background task scheduler."""

from __future__ import annotations

import asyncio

import structlog

from ..config import AppConfig
from ..core.queue import TaskStatus, TaskType
from ..intelligence.pipeline import embed_pending_chunks
from ..processing.pipeline import get_ai_pause_state
from ..storage.database import get_session

log = structlog.get_logger()


_LLM_TASK_TYPES = {TaskType.CLASSIFY.value, TaskType.EXTRACT_METADATA.value}


async def _llm_tasks_pending() -> bool:
    """Return True if any CLASSIFY or EXTRACT_METADATA tasks are pending/running."""
    from sqlalchemy import select, func
    from ..storage.models import Task
    async with get_session() as session:
        count = await session.scalar(
            select(func.count(Task.id)).where(
                Task.task_type.in_(list(_LLM_TASK_TYPES)),
                Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]),
            )
        )
        return (count or 0) > 0


async def embedding_scheduler(config: AppConfig) -> None:
    """
    Periodically generate embeddings for new chunks.

    Runs every 60 seconds.
    """
    log.info("Embedding scheduler started")

    while True:
        try:
            await asyncio.sleep(60)

            if get_ai_pause_state().is_ai_paused():
                log.debug("Embedding scheduler skipped — AI processing paused")
                continue

            # Skip embeddings while LLM tasks are running — same Ollama instance
            # can't efficiently switch between classification and embedding models.
            if await _llm_tasks_pending():
                log.debug("Embedding scheduler skipped — LLM tasks pending")
                continue

            count = await embed_pending_chunks(config)
            if count > 0:
                log.info("Background embedding complete", chunks=count)

        except asyncio.CancelledError:
            log.info("Embedding scheduler stopping")
            break
        except Exception as e:
            log.error("Embedding scheduler error", error=str(e))
            await asyncio.sleep(60)
