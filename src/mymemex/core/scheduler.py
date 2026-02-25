"""Background task scheduler."""

from __future__ import annotations

import asyncio

import structlog

from ..config import AppConfig
from ..intelligence.pipeline import embed_pending_chunks
from ..processing.pipeline import get_ai_pause_state

log = structlog.get_logger()


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

            count = await embed_pending_chunks(config)
            if count > 0:
                log.info("Background embedding complete", chunks=count)

        except asyncio.CancelledError:
            log.info("Embedding scheduler stopping")
            break
        except Exception as e:
            log.error("Embedding scheduler error", error=str(e))
            await asyncio.sleep(60)
