"""Document ingestion pipeline and task worker."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy.exc import IntegrityError

from ..config import AppConfig
from ..core.events import EventManager
from ..core.queue import TaskQueue, TaskStatus, TaskType
from ..processing.chunker import chunk_pages, chunk_text
from ..processing.extractor import extract_pdf_metadata, extract_text_from_pdf
from ..processing.ocr import ocr_page
from ..processing.hasher import hash_file, quick_fingerprint
from ..storage.database import get_session
from ..storage.models import Task
from ..storage.repositories import ChunkRepository, DocumentRepository, WatchDirectoryRepository

log = structlog.get_logger()


# Task types that use AI/LLM — suppressed when processing is paused
AI_TASK_TYPES = {"classify", "extract_metadata", "embed"}


@dataclass
class ProcessingPauseState:
    """Module-level singleton tracking whether AI/LLM processing is paused."""

    paused: bool = False
    paused_until: datetime | None = None  # None = manual resume only
    paused_at: datetime | None = None

    def is_ai_paused(self) -> bool:
        """Return True if AI processing is currently paused.

        Auto-clears if a timed pause has expired.
        """
        if not self.paused:
            return False
        if self.paused_until and datetime.now(timezone.utc) >= self.paused_until:
            self.paused = False
            self.paused_until = None
            self.paused_at = None
            return False
        return True


_ai_pause_state = ProcessingPauseState()


def get_ai_pause_state() -> ProcessingPauseState:
    """Return the module-level AI pause state singleton."""
    return _ai_pause_state


# Module-level semaphore to limit concurrent ingestion (SQLite write protection)
_ingest_semaphore: asyncio.Semaphore | None = None


def _get_ingest_semaphore(config: AppConfig) -> asyncio.Semaphore:

    """Get or create the global ingestion semaphore."""
    global _ingest_semaphore
    if _ingest_semaphore is None:
        # Use a default of 2 if not configured (should be in IngestionConfig)
        limit = getattr(config.ingestion, "max_concurrent", 2)
        _ingest_semaphore = asyncio.Semaphore(limit)
    return _ingest_semaphore


def get_mime_type(path: Path) -> str:
    """Get MIME type for a file."""
    try:
        import magic

        mime = magic.from_file(str(path), mime=True)
        return mime or "application/octet-stream"
    except Exception:
        ext = path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".txt": "text/plain",
        }
        return mime_map.get(ext, "application/octet-stream")


async def handle_new_file(
    path: Path | str,
    config: AppConfig,
    events: EventManager | None = None,
) -> None:
    """Handle a new or modified file: deduplicate and queue for ingestion."""
    path = Path(path)
    async with get_session() as session:
        repo = DocumentRepository(session)
        queue = TaskQueue(session)

        try:
            quick = quick_fingerprint(path)
        except Exception as e:
            log.error("Failed to hash file", path=str(path), error=str(e))
            return

        # Check by quick hash first
        existing = await repo.find_by_quick_hash(quick)
        if existing:
            log.info("Duplicate detected (quick hash)", path=str(path), existing_id=existing.id)
            await repo.add_file_path(existing.id, str(path))
            if events:
                await events.broadcast(
                    "document.duplicate",
                    {"path": str(path), "existing_id": existing.id},
                )
            return

        # Compute full hash
        file_hash = hash_file(path)
        existing = await repo.find_by_content_hash(file_hash.content_hash)
        if existing:
            log.info(
                "Duplicate detected (content hash)", path=str(path), existing_id=existing.id
            )
            await repo.add_file_path(existing.id, str(path))
            if events:
                await events.broadcast(
                    "document.duplicate",
                    {"path": str(path), "existing_id": existing.id},
                )
            return

        # New document
        mime_type = get_mime_type(path)
        log.info("Creating new document", path=str(path), hash=file_hash.content_hash[:8])
        try:
            doc = await repo.create(
                content_hash=file_hash.content_hash,
                quick_hash=file_hash.quick_hash,
                file_size=file_hash.file_size,
                original_path=str(path),
                original_filename=path.name,
                mime_type=mime_type,
                file_modified_at=path.stat().st_mtime,
            )
        except IntegrityError as ie:
            # Race condition or path conflict
            log.warning("IntegrityError during document creation", path=str(path), error=str(ie))
            await session.rollback()
            existing = await repo.find_by_content_hash(file_hash.content_hash)
            if existing:
                log.info("Duplicate detected (race)", path=str(path), existing_id=existing.id)
                await repo.add_file_path(existing.id, str(path))
            return

        log.info("Enqueuing INGEST task", doc_id=doc.id, path=str(path))
        await queue.enqueue(
            task_type=TaskType.INGEST,
            payload={"document_id": doc.id, "path": str(path)},
            document_id=doc.id,
            priority=5,  # Normal priority (watcher)
        )

        log.info("New document queued", doc_id=doc.id, path=str(path))

        if events:
            await events.broadcast(
                "document.discovered",
                {"id": doc.id, "path": str(path), "size_bytes": file_hash.file_size},
            )


async def run_ingest_pipeline(
    document_id: int,
    config: AppConfig,
    events: EventManager | None = None,
) -> None:
    """
    Run full ingestion pipeline for a document.

    Steps:
    1. Extract PDF metadata (title, author, page count)
    2. Extract text from PDF (PyMuPDF native)
    3. Chunk text
    4. Store chunks (triggers FTS5 indexing)
    5. Update document status
    """
    async with get_session() as session:
        repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        queue = TaskQueue(session)

        doc = await repo.get_by_id(document_id)
        if not doc:
            log.error("Document not found", doc_id=document_id)
            return

        path = Path(doc.original_path)
        if not path.exists():
            log.error("File not found", path=str(path))
            await repo.update_status(doc, "failed", error="File not found on disk")
            return

        await repo.update_status(doc, "processing")

        if events:
            await events.broadcast(
                "document.processing",
                {"id": doc.id, "step": "metadata", "progress": 0.0},
            )

        try:
                # Only process PDFs for now (images handled in M5 with OCR)
                if doc.mime_type != "application/pdf":
                    log.info("Non-PDF file, skipping text extraction", doc_id=doc.id, mime=doc.mime_type)
                    await repo.update_status(doc, "processed")
                    await repo.update(doc, processed_at=datetime.utcnow())
                    return

                # Step 1: Extract metadata
                metadata = extract_pdf_metadata(path)
                await repo.update(
                    doc,
                    page_count=metadata["page_count"],
                    title=metadata["title"],
                    author=metadata["author"],
                )

                if events:
                    await events.broadcast(
                        "document.processing",
                        {"id": doc.id, "step": "text_extraction", "progress": 0.2},
                    )

                # Step 2: Extract text page by page
                pages_with_text: list[tuple[int, str]] = []
                pages_needing_ocr: list[int] = []

                for page in extract_text_from_pdf(path):
                    if page.method == "needs_ocr":
                        pages_needing_ocr.append(page.page_number)
                        continue
                    if page.text.strip():
                        pages_with_text.append((page.page_number, page.text))

                if events:
                    await events.broadcast(
                        "document.processing",
                        {"id": doc.id, "step": "chunking", "progress": 0.4},
                    )

                # Step 3: Chunk native text and store
                all_chunks = chunk_pages(pages_with_text)
                for chunk in all_chunks:
                    await chunk_repo.create(
                        document_id=doc.id,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        text=chunk.text,
                        char_count=chunk.char_count,
                        extraction_method="pymupdf_native",
                    )

                # Step 4: OCR pages that need it
                ocr_chunk_count = 0
                if config.ocr.enabled and pages_needing_ocr:
                    log.info("Processing OCR pages", doc_id=doc.id, count=len(pages_needing_ocr))

                    if events:
                        await events.broadcast(
                            "document.processing",
                            {"id": doc.id, "step": "ocr", "progress": 0.5},
                        )

                    global_index = len(all_chunks)
                    for page_num in pages_needing_ocr:
                        text = await ocr_page(path, page_num, config.ocr)
                        if not text.strip():
                            continue

                        page_chunks = chunk_text(text, page_number=page_num)
                        for chunk in page_chunks:
                            chunk.chunk_index = global_index
                            global_index += 1
                            await chunk_repo.create(
                                document_id=doc.id,
                                chunk_index=chunk.chunk_index,
                                page_number=chunk.page_number,
                                text=chunk.text,
                                char_count=chunk.char_count,
                                extraction_method="tesseract_ocr",
                            )
                            ocr_chunk_count += 1

                await session.commit()

                # Step 5: Update document status
                await repo.update_status(doc, "processed")
                await repo.update(doc, processed_at=datetime.utcnow())

                # Step 5b: Apply file policy if a watch directory is configured
                try:
                    from ..services.file_policy import FilePolicyService

                    wd_repo = WatchDirectoryRepository(session)
                    wd = await _find_watch_directory(wd_repo, doc.original_path)
                    if wd:
                        policy_service = FilePolicyService(session)
                        await policy_service.apply(doc, wd)
                except Exception as fe:
                    log.warning("File policy apply failed", doc_id=doc.id, error=str(fe))

                total_chunks = len(all_chunks) + ocr_chunk_count
                log.info(
                    "Document ingested",
                    doc_id=doc.id,
                    native_chunks=len(all_chunks),
                    ocr_chunks=ocr_chunk_count,
                    total_chunks=total_chunks,
                    pages=metadata["page_count"],
                    pages_ocr=len(pages_needing_ocr),
                )

                # Step 6: Enqueue classification if enabled
                if config.classification.enabled and total_chunks > 0:
                    await queue.enqueue(
                        task_type=TaskType.CLASSIFY,
                        payload={"document_id": doc.id},
                        document_id=doc.id,
                        priority=3,
                    )
                    log.info("Classification task enqueued", doc_id=doc.id)

                # Step 7: Enqueue structured extraction if LLM configured
                if (
                    config.extraction.enabled
                    and config.llm.provider
                    and config.llm.provider != "none"
                    and total_chunks > 0
                ):
                    await queue.enqueue(
                        task_type=TaskType.EXTRACT_METADATA,
                        payload={"document_id": doc.id},
                        document_id=doc.id,
                        priority=2,
                    )
                    log.info("Extraction task enqueued", doc_id=doc.id)

                if events:
                    await events.broadcast(
                        "document.completed",
                        {
                            "id": doc.id,
                            "title": doc.title or doc.original_filename,
                            "chunks": total_chunks,
                            "ocr_chunks": ocr_chunk_count,
                            "pages_needing_ocr": len(pages_needing_ocr),
                        },
                    )

        except Exception as e:
            log.exception("Ingestion failed", doc_id=doc.id, error=str(e))
            await repo.update_status(doc, "failed", error=str(e))

            if events:
                await events.broadcast(
                    "document.error",
                    {"id": doc.id, "error": str(e), "retryable": True},
                )


async def task_worker(
    config: AppConfig,
    events: EventManager | None = None,
    worker_id: int = 0,
    exit_when_empty: bool = False,
) -> None:
    """Background worker that processes tasks from the queue."""
    log.info("Task worker started", worker_id=worker_id)

    # If we are in "drain" mode, wait a tiny bit for any pending commits
    if exit_when_empty:
        await asyncio.sleep(1.0)

    empty_checks = 0
    while True:
        try:
            async with get_session() as session:
                queue = TaskQueue(session)

                pause = get_ai_pause_state()
                if pause.is_ai_paused():
                    tasks = await queue.dequeue(limit=1, exclude_types=AI_TASK_TYPES)
                else:
                    tasks = await queue.dequeue(limit=1)
                if not tasks:
                    if exit_when_empty:
                        # Re-check a few times with delay to ensure no new tasks 
                        # were added by the tasks we just finished
                        if empty_checks < 3:
                            empty_checks += 1
                            await asyncio.sleep(1.0)
                            continue
                        log.info("Queue empty, worker exiting", worker_id=worker_id)
                        break
                    await asyncio.sleep(1.0)
                    continue
                
                # Reset check counter when we find work
                empty_checks = 0

                task = tasks[0]
                payload = json.loads(task.payload) if isinstance(task.payload, str) else task.payload

                try:
                    await _process_task(task, payload, config, queue, events)
                except Exception as e:
                    log.error(
                        "Task failed with exception",
                        task_id=task.id,
                        type=task.task_type,
                        error=str(e),
                        exc_info=True
                    )
                    await queue.fail(task, str(e))

        except asyncio.CancelledError:
            log.info("Task worker stopping", worker_id=worker_id)
            break
        except Exception as e:
            log.exception("Worker error", worker_id=worker_id, error=str(e))
            await asyncio.sleep(5)


async def _process_task(
    task: Task,
    payload: dict,
    config: AppConfig,
    queue: TaskQueue,
    events: EventManager | None,
) -> None:
    """Process a single task based on its type."""
    semaphore = _get_ingest_semaphore(config)

    async with semaphore:
        log.info("Processing task", task_id=task.id, type=task.task_type)

        if task.task_type == TaskType.INGEST.value:
            doc_id = payload["document_id"]
            await run_ingest_pipeline(doc_id, config, events)
            await queue.complete(task)

        elif task.task_type == TaskType.OCR_PAGE.value:
            log.warning("OCR not yet implemented (M5)", task_id=task.id)
            await queue.fail(task, "OCR not implemented in M1-M4", retryable=False)

        elif task.task_type == TaskType.CLASSIFY.value:
            from ..services.classification import ClassificationService

            doc_id = payload["document_id"]
            service = ClassificationService(config)
            await service.classify_document(doc_id)
            await queue.complete(task)

        elif task.task_type == TaskType.EXTRACT_METADATA.value:
            from ..services.extraction import ExtractionService

            doc_id = payload["document_id"]
            service = ExtractionService(config)
            await service.extract_document(doc_id)
            await queue.complete(task)

        elif task.task_type == TaskType.EMBED.value:
            log.warning("Embed task not yet implemented", task_id=task.id)
            await queue.fail(task, "Embed task not implemented", retryable=False)

        else:
            log.warning("Unknown task type", task_id=task.id, type=task.task_type)
            await queue.fail(task, f"Unknown task type: {task.task_type}", retryable=False)


async def _find_watch_directory(wd_repo: WatchDirectoryRepository, file_path: str):
    """Find which watch directory contains the given file path."""
    dirs = await wd_repo.list_active()
    for wd in dirs:
        if file_path.startswith(wd.path):
            return wd
    return None
