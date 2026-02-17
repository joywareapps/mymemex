"""Document ingestion pipeline and task worker."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import structlog

from ..config import AppConfig
from ..core.events import EventManager
from ..core.queue import TaskQueue, TaskStatus, TaskType
from ..processing.chunker import chunk_pages, chunk_text
from ..processing.extractor import extract_pdf_metadata, extract_text_from_pdf
from ..processing.ocr import ocr_page
from ..processing.hasher import hash_file, quick_fingerprint
from ..storage.database import get_session
from ..storage.models import Task
from ..storage.repositories import ChunkRepository, DocumentRepository

log = structlog.get_logger()


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
    path: Path,
    config: AppConfig,
    events: EventManager | None = None,
) -> None:
    """Handle a new or modified file: deduplicate and queue for ingestion."""
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
        doc = await repo.create(
            content_hash=file_hash.content_hash,
            quick_hash=file_hash.quick_hash,
            file_size=file_hash.file_size,
            original_path=str(path),
            original_filename=path.name,
            mime_type=mime_type,
            file_modified_at=path.stat().st_mtime,
        )

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
                await repo.update_status(doc, "ready")
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
            await repo.update_status(doc, "ready")
            await repo.update(doc, processed_at=datetime.utcnow())

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
) -> None:
    """Background worker that processes tasks from the queue."""
    log.info("Task worker started", worker_id=worker_id)

    while True:
        try:
            async with get_session() as session:
                queue = TaskQueue(session)

                tasks = await queue.dequeue(limit=1)
                if not tasks:
                    await asyncio.sleep(1)
                    continue

                task = tasks[0]
                payload = json.loads(task.payload) if isinstance(task.payload, str) else task.payload

                try:
                    await _process_task(task, payload, config, queue, events)
                except Exception as e:
                    log.exception("Task processing error", task_id=task.id)
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

    elif task.task_type == TaskType.EMBED.value:
        log.warning("Embed task not yet implemented", task_id=task.id)
        await queue.fail(task, "Embed task not implemented", retryable=False)

    else:
        log.warning("Unknown task type", task_id=task.id, type=task.task_type)
        await queue.fail(task, f"Unknown task type: {task.task_type}", retryable=False)
