"""Admin backup management endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...storage.database import get_session
from ...storage.repositories import BackupRepository

router = APIRouter()


class BackupConfigUpdate(BaseModel):
    enabled: bool | None = None
    schedule: str | None = None
    retention_days: int | None = None
    destination: str | None = None


def _backup_to_dict(b) -> dict:
    return {
        "id": b.id,
        "filename": b.filename,
        "path": b.path,
        "size_bytes": b.size_bytes,
        "status": b.status,
        "error_message": b.error_message,
        "created_at": b.created_at.isoformat(),
        "completed_at": b.completed_at.isoformat() if b.completed_at else None,
    }


@router.get("/backup/config")
async def get_backup_config(request: Request):
    config = request.app.state.config
    bc = config.backup
    return {
        "enabled": bc.enabled,
        "schedule": bc.schedule,
        "retention_days": bc.retention_days,
        "destination": bc.destination,
        "include": {
            "database": bc.include.database,
            "vectors": bc.include.vectors,
            "config": bc.include.config,
            "original_files": bc.include.original_files,
        },
    }


@router.get("/backup/history")
async def backup_history(page: int = 1, per_page: int = 20):
    async with get_session() as session:
        repo = BackupRepository(session)
        backups, total = await repo.list(page=page, per_page=per_page)
    return {
        "backups": [_backup_to_dict(b) for b in backups],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/backup/run", status_code=202)
async def run_backup(request: Request):
    """Trigger an immediate backup."""
    from ...services.backup import BackupService

    config = request.app.state.config
    if not config.backup.destination:
        raise HTTPException(status_code=422, detail="Backup destination not configured")

    async with get_session() as session:
        service = BackupService(config, session)
        backup = await service.create_backup()

    return _backup_to_dict(backup)


@router.get("/backup/{backup_id}/download")
async def download_backup(backup_id: int):
    async with get_session() as session:
        repo = BackupRepository(session)
        backup = await repo.get(backup_id)

    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    path = Path(backup.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found on disk")

    return FileResponse(
        path=str(path),
        filename=backup.filename,
        media_type="application/gzip",
    )


@router.post("/backup/restore")
async def restore_backup(backup_id: int, request: Request):
    """Restore from a recorded backup."""
    async with get_session() as session:
        repo = BackupRepository(session)
        backup = await repo.get(backup_id)

    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    config = request.app.state.config
    from ...services.backup import BackupService

    async with get_session() as session:
        service = BackupService(config, session)
        instructions = await service.restore_backup(backup.path)

    return {"status": "ready", "instructions": instructions}
