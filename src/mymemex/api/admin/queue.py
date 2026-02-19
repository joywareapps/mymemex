"""Admin task queue management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...storage.database import get_session
from ...storage.models import Task
from sqlalchemy import select, func, update

router = APIRouter()


def _task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "document_id": task.document_id,
        "attempt_count": task.attempt_count,
        "max_attempts": task.max_attempts,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.get("/queue")
async def list_queue(
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
):
    async with get_session() as session:
        query = select(Task)
        count_query = select(func.count(Task.id))

        if status:
            query = query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)

        total = await session.scalar(count_query) or 0
        offset = (page - 1) * per_page
        result = await session.execute(
            query.order_by(Task.created_at.desc()).offset(offset).limit(per_page)
        )
        tasks = list(result.scalars().all())

    return {
        "tasks": [_task_to_dict(t) for t in tasks],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/queue/{task_id}/cancel", status_code=200)
async def cancel_task(task_id: int):
    async with get_session() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status not in ("pending", "running"):
            raise HTTPException(
                status_code=409, detail=f"Cannot cancel task in status: {task.status}"
            )
        task.status = "cancelled"
        await session.commit()
    return {"status": "cancelled", "task_id": task_id}


@router.post("/queue/{task_id}/retry", status_code=200)
async def retry_task(task_id: int):
    async with get_session() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status not in ("failed", "cancelled"):
            raise HTTPException(
                status_code=409, detail=f"Cannot retry task in status: {task.status}"
            )
        task.status = "pending"
        task.attempt_count = 0
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        await session.commit()
    return {"status": "pending", "task_id": task_id}
