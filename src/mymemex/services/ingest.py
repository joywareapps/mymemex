"""Upload handling and pipeline triggering."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import AppConfig
from ..core.events import EventManager
from ..core.queue import TaskQueue, TaskType
from ..processing.pipeline import handle_new_file
from ..storage.database import get_session
from ..storage.repositories import DocumentRepository, WatchDirectoryRepository
from .exceptions import NotFoundError, ServiceError


class IngestService:
    """Upload handling and pipeline triggering."""

    def __init__(
        self,
        session: AsyncSession,
        config: AppConfig | None = None,
        events: EventManager | None = None,
    ):
        self.session = session
        self.config = config
        self.events = events
        self.doc_repo = DocumentRepository(session)

    async def _get_upload_dir(self) -> Path:
        """Get upload directory from first active watch folder (DB) or data dir."""
        async with get_session() as session:
            wd_repo = WatchDirectoryRepository(session)
            active = await wd_repo.list_active()

        if active:
            return Path(active[0].path) / "_uploads"

        # Fallback: use database directory
        if self.config:
            return self.config.database.path.parent / "_uploads"

        return Path("./data/_uploads")

    async def upload(self, content: bytes, filename: str) -> dict:
        """Save uploaded file and trigger ingestion pipeline."""
        if self.config is None:
            raise ServiceError("Configuration required for upload")

        upload_dir = await self._get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        dest = upload_dir / filename
        with open(dest, "wb") as f:
            f.write(content)

        await handle_new_file(dest, self.config, self.events)

        return {"path": str(dest), "size": len(content)}

    async def upload_from_path(
        self,
        file_path: str,
        filename: str,
        allowed_paths: list[str] | None = None,
    ) -> dict:
        """Upload a file by path (copies to inbox). Validates path boundaries."""
        if self.config is None:
            raise ServiceError("Configuration required for upload")

        source = Path(file_path).resolve()

        # Validate path exists
        if not source.exists():
            raise ServiceError(f"File not found: {file_path}")
        if not source.is_file():
            raise ServiceError(f"Not a file: {file_path}")

        # Validate path boundaries
        if allowed_paths:
            allowed = False
            for ap in allowed_paths:
                if str(source).startswith(str(Path(ap).resolve())):
                    allowed = True
                    break
            if not allowed:
                raise ServiceError(
                    f"Path not allowed: {file_path} is outside allowed directories"
                )

        upload_dir = await self._get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        dest = upload_dir / filename
        shutil.copy2(str(source), str(dest))

        await handle_new_file(dest, self.config, self.events)

        return {
            "filename": filename,
            "inbox_path": str(dest),
            "size": source.stat().st_size,
        }

    async def reprocess(self, document_id: int) -> None:
        """Re-run the ingestion pipeline for a document."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("Document not found")

        await self.doc_repo.update_status(doc, "pending")

        queue = TaskQueue(self.session)
        await queue.enqueue(
            task_type=TaskType.INGEST,
            payload={"document_id": doc.id, "path": doc.original_path},
            document_id=doc.id,
            priority=10,  # High priority (user-initiated)
        )
