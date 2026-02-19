"""Admin extended statistics endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ...storage.database import get_session
from ...storage.repositories import (
    BackupRepository,
    DocumentRepository,
    MCPTokenRepository,
    UserRepository,
    WatchDirectoryRepository,
)

router = APIRouter()


@router.get("/stats")
async def admin_stats():
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        doc_stats = await doc_repo.get_stats()

        user_repo = UserRepository(session)
        user_count = await user_repo.count()

        wd_repo = WatchDirectoryRepository(session)
        all_folders = await wd_repo.list()
        active_folders = await wd_repo.list_active()

        token_repo = MCPTokenRepository(session)
        tokens = await token_repo.list()
        active_tokens = [t for t in tokens if t.is_active]

        backup_repo = BackupRepository(session)
        backups, total_backups = await backup_repo.list(per_page=1)

    return {
        "documents": doc_stats,
        "users": {"total": user_count},
        "watch_folders": {
            "total": len(all_folders),
            "active": len(active_folders),
        },
        "mcp_tokens": {
            "total": len(tokens),
            "active": len(active_tokens),
        },
        "backups": {
            "total": total_backups,
        },
    }
