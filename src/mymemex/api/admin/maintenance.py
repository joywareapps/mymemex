"""Admin maintenance endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ...services.maintenance import ReconcileService
from ...services.system_log import system_log

router = APIRouter(prefix="/maintenance")


@router.post("/reconcile-files")
async def reconcile_files():
    """
    Reconcile all document file paths against disk.

    For each document:
    - Verifies the file exists at current_path
    - If not, finds it at original_path or by searching watch/archive dirs
    - Moves files to archive if the policy or recorded destination requires it
    - Updates current_path in DB

    Returns a report with counts per action type.
    """
    svc = ReconcileService()
    report = await svc.reconcile()

    await system_log(
        level="info",
        component="maintenance",
        message="File reconciliation complete",
        details={k: v for k, v in report.items() if k != "missing_docs"},
    )
    return report
