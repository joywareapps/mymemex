"""Document CRUD and metadata management."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.models import FilePath
from ..storage.repositories import ChunkRepository, DocumentRepository, TagRepository
from .exceptions import NotFoundError


class DocumentService:
    """Document CRUD and metadata management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.tag_repo = TagRepository(session)

    async def list_documents(
        self,
        page: int = 1,
        per_page: int = 50,
        status: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        q: str | None = None,
        sort_by: str = "ingested_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict], int]:
        """List documents with filtering and pagination."""
        documents, total = await self.doc_repo.list_documents(
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
            tags = await self.tag_repo.get_document_tags(doc.id)
            items.append({
                "id": doc.id,
                "title": doc.title,
                "original_filename": doc.original_filename,
                "original_path": doc.original_path,
                "mime_type": doc.mime_type,
                "file_size": doc.file_size,
                "page_count": doc.page_count,
                "status": doc.status,
                "category": doc.category,
                "tags": tags,
                "ingested_at": doc.ingested_at.isoformat() if doc.ingested_at else "",
                "processed_at": (
                    doc.processed_at.isoformat() if doc.processed_at else None
                ),
            })

        return items, total

    async def get_document(self, document_id: int) -> dict:
        """Get document details with chunks, tags, and file paths."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("Document not found")

        chunks = await self.chunk_repo.get_by_document(document_id)
        tags = await self.tag_repo.get_document_tags(document_id)

        # Get all file paths
        fp_result = await self.session.execute(
            select(FilePath.path).where(FilePath.document_id == document_id)
        )
        file_paths = [row[0] for row in fp_result.fetchall()]

        return {
            "id": doc.id,
            "content_hash": doc.content_hash,
            "title": doc.title,
            "original_filename": doc.original_filename,
            "original_path": doc.original_path,
            "mime_type": doc.mime_type,
            "file_size": doc.file_size,
            "page_count": doc.page_count,
            "language": doc.language,
            "author": doc.author,
            "status": doc.status,
            "category": doc.category,
            "summary": doc.summary,
            "tags": tags,
            "file_paths": file_paths,
            "chunks": [
                {
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                    "text": c.text,
                    "char_count": c.char_count,
                    "extraction_method": c.extraction_method,
                }
                for c in chunks
            ],
            "ingested_at": doc.ingested_at.isoformat() if doc.ingested_at else "",
            "processed_at": (
                doc.processed_at.isoformat() if doc.processed_at else None
            ),
            "error_count": doc.error_count or 0,
            "last_error": doc.last_error,
        }

    async def update_document(
        self,
        document_id: int,
        title: str | None = None,
        category: str | None = None,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> None:
        """Update document metadata (title, category, tags)."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("Document not found")

        updates = {}
        if title is not None:
            updates["title"] = title
        if category is not None:
            updates["category"] = category

        if updates:
            await self.doc_repo.update(doc, **updates)

        if add_tags:
            for tag_name in add_tags:
                await self.tag_repo.add_to_document(
                    document_id, tag_name, is_auto=False
                )

        if remove_tags:
            for tag_name in remove_tags:
                await self.tag_repo.remove_from_document(document_id, tag_name)

    async def get_document_text(
        self,
        document_id: int,
        page_start: int = 1,
        page_end: int | None = None,
    ) -> dict:
        """Get concatenated text for a document, optionally filtered by page range."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("Document not found")

        chunks = await self.chunk_repo.get_by_document(document_id)

        # Determine total pages from chunks
        page_numbers = [c.page_number for c in chunks if c.page_number is not None]
        total_pages = max(page_numbers) if page_numbers else len(chunks)

        if page_end is None:
            page_end = total_pages

        # Filter chunks by page range
        filtered = []
        for c in chunks:
            pn = c.page_number
            if pn is not None:
                if page_start <= pn <= page_end:
                    filtered.append(c)
            elif page_start == 1 and page_end >= total_pages:
                # Include chunks without page numbers when requesting all pages
                filtered.append(c)

        # Build per-page text
        pages = []
        for c in filtered:
            pages.append({
                "number": c.page_number or c.chunk_index + 1,
                "text": c.text,
            })

        concatenated = "\n\n".join(c.text for c in filtered)

        return {
            "document_id": document_id,
            "title": doc.title,
            "text": concatenated,
            "pages": pages,
            "total_pages": total_pages,
            "page_start": page_start,
            "page_end": page_end,
        }

    async def delete_document(self, document_id: int) -> None:
        """Remove document from index (does not delete file from disk)."""
        deleted = await self.doc_repo.delete(document_id)
        if not deleted:
            raise NotFoundError("Document not found")
