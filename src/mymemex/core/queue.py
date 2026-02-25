"""SQLite-backed task queue."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.models import Task

log = structlog.get_logger()


class TaskType(str, Enum):
    INGEST = "ingest"
    EXTRACT_TEXT = "extract_text"
    OCR_PAGE = "ocr_page"
    CHUNK = "chunk"
    EMBED = "embed"
    CLASSIFY = "classify"
    EXTRACT_METADATA = "extract_metadata"
    SUGGEST = "suggest"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_LLM = "waiting_llm"


class TaskQueue:
    """SQLite-backed async task queue with priorities and retries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        task_type: TaskType,
        payload: dict[str, Any],
        document_id: int | None = None,
        priority: int = 0,
        max_attempts: int = 3,
    ) -> Task:
        """Add a task to the queue."""
        task = Task(
            task_type=task_type.value,
            payload=json.dumps(payload),
            document_id=document_id,
            priority=priority,
            status=TaskStatus.PENDING.value,
            max_attempts=max_attempts,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        log.debug("Task enqueued", task_id=task.id, type=task_type.value)
        return task

    async def dequeue(
        self,
        task_types: list[TaskType] | None = None,
        limit: int = 1,
        exclude_types: set[str] | None = None,
    ) -> list[Task]:
        """
        Get next pending tasks, ordered by priority (desc) then created_at (asc).
        Atomically marks them as RUNNING.

        Args:
            task_types: Only dequeue tasks of these types (allowlist).
            limit: Maximum number of tasks to return.
            exclude_types: Skip tasks of these types (used to suppress AI tasks when paused).
        """
        query = (
            select(Task)
            .where(Task.status.in_([TaskStatus.PENDING.value, TaskStatus.WAITING_LLM.value]))
            .where(
                (Task.next_retry_at == None) | (Task.next_retry_at <= datetime.utcnow())  # noqa: E711
            )
            .order_by(Task.priority.desc(), Task.created_at.asc())
            .limit(limit)
        )

        if task_types:
            query = query.where(Task.task_type.in_([t.value for t in task_types]))

        if exclude_types:
            query = query.where(Task.task_type.notin_(list(exclude_types)))

        result = await self.session.execute(query)
        tasks = list(result.scalars().all())

        for task in tasks:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
            task.attempt_count += 1

        await self.session.commit()
        return tasks

    async def complete(self, task: Task) -> None:
        """Mark task as completed."""
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        await self.session.commit()
        log.debug("Task completed", task_id=task.id)

    async def fail(self, task: Task, error: str, retryable: bool = True) -> None:
        """Mark task as failed, schedule retry if possible."""
        task.error_message = error

        can_retry = retryable and task.attempt_count < task.max_attempts

        if can_retry:
            # Exponential backoff: 1m, 5m, 15m
            delays = [60, 300, 900]
            delay = delays[min(task.attempt_count - 1, len(delays) - 1)]
            task.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            task.status = TaskStatus.PENDING.value
            log.warning(
                "Task failed, will retry",
                task_id=task.id,
                attempt=task.attempt_count,
                retry_in_seconds=delay,
                error=error,
            )
        else:
            task.status = TaskStatus.FAILED.value
            log.error("Task failed permanently", task_id=task.id, error=error)

        await self.session.commit()

    async def get_stats(self) -> dict[str, int]:
        """Get queue statistics."""
        from sqlalchemy import func

        result = await self.session.execute(
            select(Task.status, func.count(Task.id)).group_by(Task.status)
        )
        stats: dict[str, int] = {}
        for row in result.fetchall():
            stats[row[0]] = row[1]
        return stats

    async def recover_stale(self, timeout_minutes: int = 30) -> int:
        """Reset tasks stuck in RUNNING state (e.g., after crash)."""
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        result = await self.session.execute(
            update(Task)
            .where(Task.status == TaskStatus.RUNNING.value)
            .where(Task.started_at < cutoff)
            .values(status=TaskStatus.PENDING.value, started_at=None)
        )
        await self.session.commit()
        count = result.rowcount  # type: ignore[attr-defined]
        if count:
            log.warning("Recovered stale tasks", count=count)
        return count
