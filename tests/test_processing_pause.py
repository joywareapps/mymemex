"""Tests for AI processing pause/resume feature."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from mymemex.app import create_app
from mymemex.core.queue import TaskQueue, TaskType
from mymemex.processing.pipeline import (
    AI_TASK_TYPES,
    ProcessingPauseState,
    get_ai_pause_state,
)


# ---------------------------------------------------------------------------
# ProcessingPauseState unit tests
# ---------------------------------------------------------------------------


def test_not_paused_initially():
    """A freshly created state reports not paused."""
    state = ProcessingPauseState()
    assert state.is_ai_paused() is False


def test_paused_indefinitely():
    """paused=True with no paused_until → always paused."""
    state = ProcessingPauseState(paused=True)
    assert state.is_ai_paused() is True


def test_paused_until_future():
    """paused=True with paused_until in the future → still paused."""
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    state = ProcessingPauseState(paused=True, paused_until=future)
    assert state.is_ai_paused() is True


def test_paused_until_expired_auto_clears():
    """paused=True with paused_until in the past → auto-clears, returns False."""
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    state = ProcessingPauseState(paused=True, paused_until=past, paused_at=past)
    assert state.is_ai_paused() is False
    # State should be cleared
    assert state.paused is False
    assert state.paused_until is None
    assert state.paused_at is None


def test_resume_clears_state():
    """Simulating resume by clearing state fields returns False."""
    state = ProcessingPauseState(
        paused=True,
        paused_at=datetime.now(timezone.utc),
    )
    state.paused = False
    state.paused_until = None
    state.paused_at = None
    assert state.is_ai_paused() is False


# ---------------------------------------------------------------------------
# TaskQueue.dequeue exclude_types test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dequeue_exclude_ai_types_skips_classify(db_session):
    """dequeue(exclude_types=AI_TASK_TYPES) should skip CLASSIFY but return INGEST."""
    queue = TaskQueue(db_session)

    await queue.enqueue(
        task_type=TaskType.CLASSIFY,
        payload={"document_id": 1},
        priority=10,  # higher priority — must be skipped
    )
    ingest_task = await queue.enqueue(
        task_type=TaskType.INGEST,
        payload={"document_id": 1, "path": "/tmp/test.pdf"},
        priority=5,
    )

    tasks = await queue.dequeue(limit=1, exclude_types=AI_TASK_TYPES)
    assert len(tasks) == 1
    assert tasks[0].id == ingest_task.id
    assert tasks[0].task_type == TaskType.INGEST.value


# ---------------------------------------------------------------------------
# Admin API tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client(test_config):
    """Create test client with lifespan (initializes DB)."""
    app = create_app(test_config)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_pause_state():
    """Reset the global pause state before each test."""
    state = get_ai_pause_state()
    state.paused = False
    state.paused_until = None
    state.paused_at = None
    yield
    state.paused = False
    state.paused_until = None
    state.paused_at = None


def test_status_default_not_paused(client):
    """GET /admin/processing/status returns paused=false by default."""
    resp = client.get("/api/v1/admin/processing/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paused"] is False
    assert data["paused_until"] is None
    assert data["ai_tasks_pending"] == 0


def test_pause_timed(client):
    """POST /admin/processing/pause with minutes=60 sets state."""
    resp = client.post(
        "/api/v1/admin/processing/pause",
        json={"minutes": 60},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paused"] is True
    assert data["paused_until"] is not None

    # Verify via status endpoint
    status = client.get("/api/v1/admin/processing/status").json()
    assert status["paused"] is True
    assert status["paused_until"] is not None


def test_pause_indefinite(client):
    """POST /admin/processing/pause with no minutes → indefinite pause."""
    resp = client.post("/api/v1/admin/processing/pause", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["paused"] is True
    assert data["paused_until"] is None

    status = client.get("/api/v1/admin/processing/status").json()
    assert status["paused"] is True
    assert status["paused_until"] is None


def test_resume_clears_pause(client):
    """POST /admin/processing/resume clears pause state."""
    # First pause
    client.post("/api/v1/admin/processing/pause", json={"minutes": 60})

    # Then resume
    resp = client.post("/api/v1/admin/processing/resume")
    assert resp.status_code == 200
    assert resp.json()["paused"] is False

    status = client.get("/api/v1/admin/processing/status").json()
    assert status["paused"] is False
