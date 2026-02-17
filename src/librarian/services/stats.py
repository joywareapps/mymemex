"""Library statistics aggregation."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import AppConfig
from ..core.queue import TaskQueue
from ..storage.repositories import ChunkRepository, DocumentRepository


class StatsService:
    """Library statistics aggregation."""

    def __init__(self, session: AsyncSession, config: AppConfig):
        self.session = session
        self.config = config
        self.doc_repo = DocumentRepository(session)
        self.chunk_repo = ChunkRepository(session)

    async def get_library_stats(self) -> dict:
        """Get library statistics (documents, chunks, queue, storage)."""
        doc_stats = await self.doc_repo.get_stats()
        total_chunks = await self.chunk_repo.get_total_count()

        queue = TaskQueue(self.session)
        queue_stats = await queue.get_stats()

        db_path = Path(self.config.database.path)
        sqlite_size_mb = (
            db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
        )

        return {
            "doc_stats": doc_stats,
            "total_chunks": total_chunks,
            "queue_stats": queue_stats,
            "sqlite_size_mb": round(sqlite_size_mb, 2),
        }
