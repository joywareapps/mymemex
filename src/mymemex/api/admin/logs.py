"""Admin log endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ...storage.database import get_session
from ...storage.repositories import FileOperationLogRepository, SystemLogRepository

router = APIRouter()


def _file_op_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "document_id": entry.document_id,
        "operation": entry.operation,
        "source_path": entry.source_path,
        "destination_path": entry.destination_path,
        "status": entry.status,
        "error_message": entry.error_message,
        "created_at": entry.created_at.isoformat(),
    }


def _sys_log_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "level": entry.level,
        "component": entry.component,
        "message": entry.message,
        "details": entry.details,
        "created_at": entry.created_at.isoformat(),
    }


@router.get("/logs/file-ops")
async def list_file_op_logs(
    document_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
):
    async with get_session() as session:
        repo = FileOperationLogRepository(session)
        entries, total = await repo.list(
            document_id=document_id,
            status=status,
            page=page,
            per_page=per_page,
        )
    return {
        "entries": [_file_op_to_dict(e) for e in entries],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/logs/system")
async def list_system_logs(
    level: str | None = None,
    component: str | None = None,
    page: int = 1,
    per_page: int = 100,
):
    async with get_session() as session:
        repo = SystemLogRepository(session)
        entries, total = await repo.list(
            level=level,
            component=component,
            page=page,
            per_page=per_page,
        )
    return {
        "entries": [_sys_log_to_dict(e) for e in entries],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
