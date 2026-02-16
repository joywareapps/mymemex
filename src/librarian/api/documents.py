"""Document CRUD API endpoints."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from ..core.queue import TaskQueue, TaskType
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentRepository, TagRepository

router = APIRouter()


# --- Schemas ---


class DocumentSummary(BaseModel):
    id: int
    title: str | None
    original_filename: str
    original_path: str
    mime_type: str
    file_size: int
    page_count: int | None
    status: str
    category: str | None
    tags: list[str] = []
    ingested_at: str
    processed_at: str | None


class DocumentDetail(BaseModel):
    id: int
    content_hash: str
    title: str | None
    original_filename: str
    original_path: str
    mime_type: str
    file_size: int
    page_count: int | None
    language: str | None
    author: str | None
    status: str
    category: str | None
    summary: str | None
    tags: list[str] = []
    file_paths: list[str] = []
    chunks: list[ChunkInfo] = []
    ingested_at: str
    processed_at: str | None
    error_count: int
    last_error: str | None


class ChunkInfo(BaseModel):
    chunk_index: int
    page_number: int | None
    text: str
    char_count: int
    extraction_method: str | None


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    total: int
    page: int
    per_page: int


class DocumentPatch(BaseModel):
    title: str | None = None
    category: str | None = None
    add_tags: list[str] | None = None
    remove_tags: list[str] | None = None


# --- Endpoints ---


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    sort_by: str = "ingested_at",
    sort_order: str = "desc",
):
    """List documents with filtering and pagination."""
    async with get_session() as session:
        repo = DocumentRepository(session)
        tag_repo = TagRepository(session)

        documents, total = await repo.list_documents(
            page=page,
            per_page=per_page,
            status=status,
            category=category,
            tag=tag,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        items = []
        for doc in documents:
            tags = await tag_repo.get_document_tags(doc.id)
            items.append(
                DocumentSummary(
                    id=doc.id,
                    title=doc.title,
                    original_filename=doc.original_filename,
                    original_path=doc.original_path,
                    mime_type=doc.mime_type,
                    file_size=doc.file_size,
                    page_count=doc.page_count,
                    status=doc.status,
                    category=doc.category,
                    tags=tags,
                    ingested_at=doc.ingested_at.isoformat() if doc.ingested_at else "",
                    processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
                )
            )

        return DocumentListResponse(
            documents=items,
            total=total,
            page=page,
            per_page=per_page,
        )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: int):
    """Get document details with chunks."""
    async with get_session() as session:
        repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        tag_repo = TagRepository(session)

        doc = await repo.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = await chunk_repo.get_by_document(document_id)
        tags = await tag_repo.get_document_tags(document_id)

        # Get all file paths
        from sqlalchemy import select
        from ..storage.models import FilePath

        fp_result = await session.execute(
            select(FilePath.path).where(FilePath.document_id == document_id)
        )
        file_paths = [row[0] for row in fp_result.fetchall()]

        return DocumentDetail(
            id=doc.id,
            content_hash=doc.content_hash,
            title=doc.title,
            original_filename=doc.original_filename,
            original_path=doc.original_path,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            page_count=doc.page_count,
            language=doc.language,
            author=doc.author,
            status=doc.status,
            category=doc.category,
            summary=doc.summary,
            tags=tags,
            file_paths=file_paths,
            chunks=[
                ChunkInfo(
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    text=c.text,
                    char_count=c.char_count,
                    extraction_method=c.extraction_method,
                )
                for c in chunks
            ],
            ingested_at=doc.ingested_at.isoformat() if doc.ingested_at else "",
            processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
            error_count=doc.error_count or 0,
            last_error=doc.last_error,
        )


@router.patch("/{document_id}")
async def update_document(document_id: int, patch: DocumentPatch):
    """Update document metadata (title, category, tags)."""
    async with get_session() as session:
        repo = DocumentRepository(session)
        tag_repo = TagRepository(session)

        doc = await repo.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        updates = {}
        if patch.title is not None:
            updates["title"] = patch.title
        if patch.category is not None:
            updates["category"] = patch.category

        if updates:
            await repo.update(doc, **updates)

        if patch.add_tags:
            for tag_name in patch.add_tags:
                await tag_repo.add_to_document(document_id, tag_name, is_auto=False)

        if patch.remove_tags:
            for tag_name in patch.remove_tags:
                await tag_repo.remove_from_document(document_id, tag_name)

        return {"status": "updated", "id": document_id}


@router.delete("/{document_id}")
async def delete_document(document_id: int):
    """Remove document from index (does not delete file from disk)."""
    async with get_session() as session:
        repo = DocumentRepository(session)
        deleted = await repo.delete(document_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "deleted", "id": document_id}


@router.post("/{document_id}/reprocess")
async def reprocess_document(document_id: int):
    """Re-run the ingestion pipeline for a document."""
    async with get_session() as session:
        repo = DocumentRepository(session)
        queue = TaskQueue(session)

        doc = await repo.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        await repo.update_status(doc, "pending")

        await queue.enqueue(
            task_type=TaskType.INGEST,
            payload={"document_id": doc.id, "path": doc.original_path},
            document_id=doc.id,
            priority=10,  # High priority (user-initiated)
        )

        return {"status": "queued", "id": document_id}


@router.post("/upload")
async def upload_document(file: UploadFile, request: Request):
    """Upload a file for processing."""
    config = request.app.state.config

    # Save to a temporary location in the first watch directory
    if not config.watch.directories:
        raise HTTPException(
            status_code=400,
            detail="No watch directories configured",
        )

    upload_dir = Path(config.watch.directories[0]).expanduser() / "_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    # The watcher will pick it up, but let's also trigger directly
    from ..processing.pipeline import handle_new_file

    events = getattr(request.app.state, "events", None)
    await handle_new_file(dest, config, events)

    return {"status": "uploaded", "path": str(dest), "size": len(content)}
