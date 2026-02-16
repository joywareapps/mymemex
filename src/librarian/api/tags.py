"""Tag management API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..storage.database import get_session
from ..storage.repositories import TagRepository

router = APIRouter()


class TagInfo(BaseModel):
    id: int
    name: str
    color: str | None
    document_count: int


class TagCreate(BaseModel):
    name: str
    color: str | None = None


@router.get("", response_model=list[TagInfo])
async def list_tags():
    """List all tags with document counts."""
    async with get_session() as session:
        repo = TagRepository(session)
        tags = await repo.list_with_counts()
        return [TagInfo(**t) for t in tags]


@router.post("", response_model=TagInfo)
async def create_tag(body: TagCreate):
    """Create a new tag."""
    async with get_session() as session:
        repo = TagRepository(session)
        tag = await repo.get_or_create(body.name)
        await session.commit()
        return TagInfo(id=tag.id, name=tag.name, color=tag.color, document_count=0)


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int):
    """Delete a tag (unlinks from all documents)."""
    async with get_session() as session:
        repo = TagRepository(session)
        deleted = await repo.delete(tag_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Tag not found")
        return {"status": "deleted", "id": tag_id}
