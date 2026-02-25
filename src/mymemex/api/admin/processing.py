"""Admin endpoints for AI processing pause/resume control."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from ...core.queue import TaskStatus
from ...processing.pipeline import AI_TASK_TYPES, get_ai_pause_state
from ...services.system_log import system_log
from ...storage.database import get_session
from ...storage.models import Task

router = APIRouter(prefix="/processing")


class PauseRequest(BaseModel):
    minutes: int | None = None  # None = pause indefinitely


@router.get("/status")
async def get_processing_status():
    """Return current AI processing pause state and pending AI task count."""
    state = get_ai_pause_state()
    paused = state.is_ai_paused()

    async with get_session() as session:
        result = await session.scalar(
            select(func.count(Task.id)).where(
                Task.status == TaskStatus.PENDING.value,
                Task.task_type.in_(list(AI_TASK_TYPES)),
            )
        )
        ai_tasks_pending = result or 0

    return {
        "paused": paused,
        "paused_until": state.paused_until.isoformat() if state.paused_until else None,
        "paused_at": state.paused_at.isoformat() if state.paused_at else None,
        "ai_tasks_pending": ai_tasks_pending,
    }


@router.post("/pause", status_code=200)
async def pause_processing(body: PauseRequest = PauseRequest()):
    """Pause AI/LLM task processing (CLASSIFY, EXTRACT_METADATA, embeddings).

    In-flight tasks complete normally. Only new dequeues are suppressed.
    App restart always clears the pause.
    """
    state = get_ai_pause_state()
    now = datetime.now(timezone.utc)

    state.paused = True
    state.paused_at = now
    state.paused_until = now + timedelta(minutes=body.minutes) if body.minutes else None

    duration_desc = f"{body.minutes} minutes" if body.minutes else "indefinitely"
    await system_log(
        level="info",
        component="processing",
        message=f"AI processing paused {duration_desc}",
        details={"minutes": body.minutes, "paused_until": state.paused_until.isoformat() if state.paused_until else None},
    )

    return {
        "paused": True,
        "paused_until": state.paused_until.isoformat() if state.paused_until else None,
        "paused_at": state.paused_at.isoformat(),
    }


@router.post("/resume", status_code=200)
async def resume_processing():
    """Resume AI/LLM task processing."""
    state = get_ai_pause_state()
    state.paused = False
    state.paused_until = None
    state.paused_at = None

    await system_log(
        level="info",
        component="processing",
        message="AI processing resumed",
    )

    return {"paused": False}
