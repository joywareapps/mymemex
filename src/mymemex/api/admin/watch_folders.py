"""Admin watch folder CRUD endpoints."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...storage.database import get_session
from ...storage.repositories import WatchDirectoryRepository

router = APIRouter()


class WatchFolderCreate(BaseModel):
    path: str
    patterns: list[str] = []
    is_active: bool = True
    file_policy: str = "keep_original"
    archive_path: str | None = None
    rename_template: str | None = None


class WatchFolderUpdate(BaseModel):
    patterns: list[str] | None = None
    is_active: bool | None = None
    file_policy: str | None = None
    archive_path: str | None = None
    rename_template: str | None = None


def _wd_to_dict(wd) -> dict:
    return {
        "id": wd.id,
        "path": wd.path,
        "patterns": json.loads(wd.patterns or "[]"),
        "is_active": wd.is_active,
        "file_policy": wd.file_policy,
        "archive_path": wd.archive_path,
        "rename_template": wd.rename_template,
        "created_at": wd.created_at.isoformat(),
        "updated_at": wd.updated_at.isoformat() if wd.updated_at else None,
    }


@router.get("/watch-folders")
async def list_watch_folders():
    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        folders = await repo.list()
    return {"folders": [_wd_to_dict(f) for f in folders]}


@router.post("/watch-folders", status_code=201)
async def create_watch_folder(body: WatchFolderCreate, request: Request):
    path = str(Path(body.path).expanduser())
    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        existing = await repo.get_by_path(path)
        if existing:
            raise HTTPException(status_code=409, detail="Watch folder already exists")
        wd = await repo.create(
            path=path,
            patterns=json.dumps(body.patterns),
            is_active=body.is_active,
            file_policy=body.file_policy,
            archive_path=body.archive_path,
            rename_template=body.rename_template,
        )
        result = _wd_to_dict(wd)

    # Dynamically register with running watcher
    watcher = getattr(request.app.state, "watcher", None)
    if watcher and body.is_active:
        watcher.add_directory(path)

    return result


@router.get("/watch-folders/{folder_id}")
async def get_watch_folder(folder_id: int):
    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        wd = await repo.get(folder_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch folder not found")
        return _wd_to_dict(wd)


@router.patch("/watch-folders/{folder_id}")
async def update_watch_folder(folder_id: int, body: WatchFolderUpdate, request: Request):
    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        wd = await repo.get(folder_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch folder not found")

        kwargs = {}
        if body.patterns is not None:
            kwargs["patterns"] = json.dumps(body.patterns)
        if body.is_active is not None:
            kwargs["is_active"] = body.is_active
        if body.file_policy is not None:
            kwargs["file_policy"] = body.file_policy
        if body.archive_path is not None:
            kwargs["archive_path"] = body.archive_path
        if body.rename_template is not None:
            kwargs["rename_template"] = body.rename_template

        await repo.update(wd, **kwargs)
        path = wd.path
        result = _wd_to_dict(wd)

    # Sync with watcher
    watcher = getattr(request.app.state, "watcher", None)
    if watcher:
        if body.is_active is True:
            watcher.add_directory(path)
        elif body.is_active is False:
            watcher.remove_directory(path)

    return result


@router.delete("/watch-folders/{folder_id}", status_code=204)
async def delete_watch_folder(folder_id: int, request: Request):
    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        wd = await repo.get(folder_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch folder not found")
        path = wd.path
        deleted = await repo.delete(folder_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Watch folder not found")

    watcher = getattr(request.app.state, "watcher", None)
    if watcher:
        watcher.remove_directory(path)


@router.post("/watch-folders/{folder_id}/test-access")
async def test_watch_folder_access(folder_id: int):
    """Test write/delete access to the archive path by creating and removing a temp file."""
    import tempfile
    import os

    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        wd = await repo.get(folder_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch folder not found")
        archive_path = wd.archive_path

    if not archive_path:
        raise HTTPException(status_code=422, detail="No archive path configured on this watch folder")

    dest = Path(archive_path)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": f"Cannot create archive directory: {e}"}

    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".mymemex_test_", dir=dest)
        os.close(fd)
        os.unlink(tmp_path)
    except Exception as e:
        return {"ok": False, "error": f"Cannot write/delete in archive path: {e}"}

    return {"ok": True, "path": str(dest)}


@router.post("/watch-folders/{folder_id}/rescan")
async def rescan_watch_folder(folder_id: int, request: Request):
    """Trigger a rescan of all files in a watch folder."""
    async with get_session() as session:
        repo = WatchDirectoryRepository(session)
        wd = await repo.get(folder_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch folder not found")
        path = Path(wd.path)

    if not path.exists():
        raise HTTPException(status_code=422, detail="Directory does not exist on disk")

    # Start rescan in background
    from ...processing.rescan import rescan_directory
    config = request.app.state.config
    events = request.app.state.events
    
    # We don't await this, just fire and forget into the event loop
    async def _run():
        try:
            await rescan_directory(path, config, events)
        except Exception as e:
            import structlog
            structlog.get_logger().error("Rescan task failed", path=str(path), error=str(e), exc_info=True)
    asyncio.create_task(_run())

    # Count files to scan for immediate feedback
    file_count = sum(1 for _ in path.rglob("*") if _.is_file())
    return {"status": "scheduled", "path": str(path), "file_count": file_count}
