"""File policy execution service."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.models import Document, FilePolicy, WatchDirectory
from ..storage.repositories import FileOperationLogRepository

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

_TEMPLATE_VARS = {
    "date", "year", "month", "day",
    "category", "title", "original_name", "ext", "hash",
}


def _render_template(template: str, doc: Document) -> str:
    """Substitute template variables for a document."""
    now = datetime.utcnow()
    values = {
        "date": now.strftime("%Y-%m-%d"),
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "category": doc.category or "other",
        "title": _safe_filename(doc.title or doc.original_filename),
        "original_name": Path(doc.original_filename).stem,
        "ext": Path(doc.original_filename).suffix,
        "hash": doc.content_hash[:8] if doc.content_hash else "00000000",
    }
    try:
        return template.format(**values)
    except KeyError:
        return template  # Return as-is on template error


def _safe_filename(name: str) -> str:
    """Remove characters unsafe for filenames."""
    unsafe = r'\/:*?"<>|'
    for ch in unsafe:
        name = name.replace(ch, "_")
    return name.strip()[:100]


def _resolve_conflict(dest: Path) -> Path:
    """Append hash suffix if destination already exists."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    import hashlib
    salt = hashlib.md5(str(dest).encode()).hexdigest()[:8]
    return parent / f"{stem}-{salt}{suffix}"


class FilePolicyService:
    """Apply file policies after document ingestion."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.log_repo = FileOperationLogRepository(session)

    async def apply(self, doc: Document, watch_dir: WatchDirectory) -> None:
        """Apply the watch directory's file policy to the document."""
        policy = watch_dir.file_policy or FilePolicy.keep_original.value

        # Prefer current_path (file may already be in archive from a previous run)
        _orig = Path(doc.original_path)
        _cur = Path(doc.current_path) if doc.current_path else None
        source = _cur if (_cur and _cur.exists()) else _orig

        # If the file is already inside the target archive directory, nothing to do
        if watch_dir.archive_path and str(source).startswith(watch_dir.archive_path):
            return

        if policy == FilePolicy.keep_original.value:
            return  # Nothing to do

        try:
            if policy == FilePolicy.delete_original.value:
                await self._delete(doc, source)

            elif policy == FilePolicy.move_to_archive.value:
                dest_dir = Path(watch_dir.archive_path or "./archive")
                dest = _resolve_conflict(dest_dir / doc.original_filename)
                await self._move(doc, source, dest)

            elif policy == FilePolicy.copy_organized.value:
                dest_dir = Path(watch_dir.archive_path or "./organized")
                dest = _resolve_conflict(dest_dir / doc.original_filename)
                await self._copy(doc, source, dest)

            elif policy == FilePolicy.rename_template.value:
                template = watch_dir.rename_template or "{date}-{original_name}{ext}"
                new_name = _render_template(template, doc)
                dest = _resolve_conflict(source.parent / new_name)
                await self._move(doc, source, dest)

        except Exception as e:
            log.error("File policy failed", policy=policy, path=str(source), error=str(e))
            await self.log_repo.create(
                operation=f"policy:{policy}",
                source_path=str(source),
                status="failed",
                document_id=doc.id,
                error_message=str(e),
            )

    async def _move(self, doc: Document, source: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))

        doc.current_path = str(dest)
        doc.file_policy_applied = "move_to_archive"
        await self.session.commit()

        await self.log_repo.create(
            operation="move",
            source_path=str(source),
            destination_path=str(dest),
            status="success",
            document_id=doc.id,
        )
        log.info("File moved", src=str(source), dest=str(dest))

    async def _copy(self, doc: Document, source: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(dest))

        doc.current_path = str(dest)
        doc.file_policy_applied = "copy_organized"
        await self.session.commit()

        await self.log_repo.create(
            operation="copy",
            source_path=str(source),
            destination_path=str(dest),
            status="success",
            document_id=doc.id,
        )
        log.info("File copied", src=str(source), dest=str(dest))

    async def _delete(self, doc: Document, source: Path) -> None:
        if source.exists():
            source.unlink()

        doc.file_policy_applied = "delete_original"
        await self.session.commit()

        await self.log_repo.create(
            operation="delete",
            source_path=str(source),
            status="success",
            document_id=doc.id,
        )
        log.info("File deleted", path=str(source))
