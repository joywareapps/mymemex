"""Tag management API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import NotFoundError
from ..services.tag import TagService
from ..storage.database import get_session

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
        service = TagService(session)
        tags = await service.list_tags()
        return [TagInfo(**t) for t in tags]


@router.post("", response_model=TagInfo)
async def create_tag(body: TagCreate):
    """Create a new tag."""
    async with get_session() as session:
        service = TagService(session)
        result = await service.create_tag(body.name, body.color)
        return TagInfo(**result)


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int):
    """Delete a tag (unlinks from all documents)."""
    async with get_session() as session:
        service = TagService(session)
        try:
            await service.delete_tag(tag_id)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Tag not found")

        return {"status": "deleted", "id": tag_id}
