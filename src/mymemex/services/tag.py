"""Tag CRUD and assignment operations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.repositories import DocumentRepository, TagRepository
from .exceptions import NotFoundError


class TagService:
    """Tag CRUD and assignment operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tag_repo = TagRepository(session)
        self.doc_repo = DocumentRepository(session)

    async def list_tags(self) -> list[dict]:
        """List all tags with document counts."""
        return await self.tag_repo.list_with_counts()

    async def create_tag(self, name: str, color: str | None = None) -> dict:
        """Create a new tag."""
        tag = await self.tag_repo.get_or_create(name)
        await self.session.commit()
        return {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "document_count": 0,
        }

    async def add_tag_to_document(self, document_id: int, tag_name: str) -> dict:
        """Add a tag to a document."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError(f"Document {document_id} not found")

        # Check if tag already exists (to report is_new)
        existing_tags = await self.tag_repo.get_document_tags(document_id)
        is_new = tag_name not in existing_tags

        await self.tag_repo.add_to_document(document_id, tag_name, is_auto=False)

        return {"document_id": document_id, "tag": tag_name, "is_new": is_new}

    async def remove_tag_from_document(self, document_id: int, tag_name: str) -> dict:
        """Remove a tag from a document."""
        doc = await self.doc_repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError(f"Document {document_id} not found")

        removed = await self.tag_repo.remove_from_document(document_id, tag_name)
        if not removed:
            raise NotFoundError(f"Tag '{tag_name}' not found on document {document_id}")

        return {"document_id": document_id, "tag": tag_name}

    async def delete_tag(self, tag_id: int) -> None:
        """Delete a tag (unlinks from all documents)."""
        deleted = await self.tag_repo.delete(tag_id)
        if not deleted:
            raise NotFoundError("Tag not found")
