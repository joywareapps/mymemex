"""Admin setup status endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ...storage.database import get_session
from ...storage.repositories import UserRepository

router = APIRouter()


@router.get("/setup/status")
async def setup_status():
    """Return whether initial setup is needed (no users exist)."""
    async with get_session() as session:
        repo = UserRepository(session)
        count = await repo.count()
    return {"needs_setup": count == 0}
