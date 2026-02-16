"""Tests for SQLite-backed task queue."""

from __future__ import annotations

import pytest

from librarian.core.queue import TaskQueue, TaskStatus, TaskType


@pytest.mark.asyncio
async def test_enqueue_dequeue(db_session):
    """Should enqueue and dequeue a task."""
    queue = TaskQueue(db_session)

    task = await queue.enqueue(
        task_type=TaskType.INGEST,
        payload={"document_id": 1, "path": "/tmp/test.pdf"},
        priority=5,
    )
    assert task.id is not None
    assert task.status == TaskStatus.PENDING.value

    tasks = await queue.dequeue(limit=1)
    assert len(tasks) == 1
    assert tasks[0].id == task.id
    assert tasks[0].status == TaskStatus.RUNNING.value
    assert tasks[0].attempt_count == 1


@pytest.mark.asyncio
async def test_complete_task(db_session):
    """Should mark task as completed."""
    queue = TaskQueue(db_session)

    task = await queue.enqueue(
        task_type=TaskType.INGEST,
        payload={"test": True},
    )
    tasks = await queue.dequeue(limit=1)
    await queue.complete(tasks[0])

    assert tasks[0].status == TaskStatus.COMPLETED.value
    assert tasks[0].completed_at is not None


@pytest.mark.asyncio
async def test_fail_with_retry(db_session):
    """Failed task should be rescheduled if retryable."""
    queue = TaskQueue(db_session)

    task = await queue.enqueue(
        task_type=TaskType.INGEST,
        payload={"test": True},
        max_attempts=3,
    )
    tasks = await queue.dequeue(limit=1)
    await queue.fail(tasks[0], "Connection error")

    assert tasks[0].status == TaskStatus.PENDING.value
    assert tasks[0].next_retry_at is not None
    assert tasks[0].error_message == "Connection error"


@pytest.mark.asyncio
async def test_fail_permanently(db_session):
    """Non-retryable failure should mark task as failed."""
    queue = TaskQueue(db_session)

    task = await queue.enqueue(
        task_type=TaskType.INGEST,
        payload={"test": True},
    )
    tasks = await queue.dequeue(limit=1)
    await queue.fail(tasks[0], "Unknown task type", retryable=False)

    assert tasks[0].status == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_priority_ordering(db_session):
    """Higher priority tasks should be dequeued first."""
    queue = TaskQueue(db_session)

    await queue.enqueue(task_type=TaskType.INGEST, payload={"id": "low"}, priority=1)
    await queue.enqueue(task_type=TaskType.INGEST, payload={"id": "high"}, priority=10)
    await queue.enqueue(task_type=TaskType.INGEST, payload={"id": "mid"}, priority=5)

    tasks = await queue.dequeue(limit=3)
    priorities = [t.priority for t in tasks]
    assert priorities == sorted(priorities, reverse=True)


@pytest.mark.asyncio
async def test_get_stats(db_session):
    """get_stats should return status counts."""
    queue = TaskQueue(db_session)
    stats = await queue.get_stats()
    assert isinstance(stats, dict)


@pytest.mark.asyncio
async def test_recover_stale(db_session):
    """recover_stale should reset stuck tasks."""
    queue = TaskQueue(db_session)
    recovered = await queue.recover_stale(timeout_minutes=0)
    assert isinstance(recovered, int)
