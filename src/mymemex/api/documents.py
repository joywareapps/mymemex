"""Document CRUD API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from ..services import NotFoundError, ServiceError
from ..services.document import DocumentService
from ..services.ingest import IngestService
from ..storage.database import get_session

from fastapi.responses import FileResponse
import os

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
        service = DocumentService(session)
        items, total = await service.list_documents(
            page=page,
            per_page=per_page,
            status=status,
            category=category,
            tag=tag,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return DocumentListResponse(
            documents=[DocumentSummary(**d) for d in items],
            total=total,
            page=page,
            per_page=per_page,
        )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: int):
    """Get document details with chunks."""
    async with get_session() as session:
        service = DocumentService(session)
        try:
            data = await service.get_document(document_id)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentDetail(
            **{k: v for k, v in data.items() if k != "chunks"},
            chunks=[ChunkInfo(**c) for c in data["chunks"]],
        )


@router.get("/{document_id}/download")
async def download_document(document_id: int, inline: bool = False):
    """Download the original document file. Pass ?inline=true to render in browser."""
    async with get_session() as session:
        service = DocumentService(session)
        try:
            doc_data = await service.get_document(document_id)
            path = doc_data["original_path"]
            filename = doc_data["original_filename"]

            if not os.path.exists(path):
                raise HTTPException(status_code=404, detail="File not found on disk")

            if inline:
                return FileResponse(
                    path,
                    media_type=doc_data["mime_type"],
                    headers={"Content-Disposition": f"inline; filename=\"{filename}\""},
                )
            return FileResponse(
                path,
                filename=filename,
                media_type=doc_data["mime_type"],
            )
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")


@router.patch("/{document_id}")
async def update_document(document_id: int, patch: DocumentPatch):
    """Update document metadata (title, category, tags)."""
    async with get_session() as session:
        service = DocumentService(session)
        try:
            await service.update_document(
                document_id,
                title=patch.title,
                category=patch.category,
                add_tags=patch.add_tags,
                remove_tags=patch.remove_tags,
            )
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"status": "updated", "id": document_id}


@router.delete("/{document_id}")
async def delete_document(document_id: int):
    """Remove document from index (does not delete file from disk)."""
    async with get_session() as session:
        service = DocumentService(session)
        try:
            await service.delete_document(document_id)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"status": "deleted", "id": document_id}


@router.post("/{document_id}/reprocess")
async def reprocess_document(document_id: int):
    """Re-run the ingestion pipeline for a document."""
    async with get_session() as session:
        service = IngestService(session)
        try:
            await service.reprocess(document_id)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")

        return {"status": "queued", "id": document_id}


@router.post("/upload")
async def upload_document(file: UploadFile, request: Request):
    """Upload a file for processing."""
    config = request.app.state.config
    content = await file.read()

    async with get_session() as session:
        events = getattr(request.app.state, "events", None)
        service = IngestService(session, config, events)
        try:
            result = await service.upload(content, file.filename)
        except ServiceError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {"status": "uploaded", **result}
