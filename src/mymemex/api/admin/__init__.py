"""Admin API package."""

from fastapi import APIRouter

from .backup import router as backup_router
from .config_admin import router as config_router
from .logs import router as logs_router
from .mcp import router as mcp_router
from .processing import router as processing_router
from .queue import router as queue_router
from .setup import router as setup_router
from .stats import router as stats_router
from .users import router as users_router
from .watch_folders import router as watch_folders_router

admin_router = APIRouter(tags=["admin"])

admin_router.include_router(setup_router)
admin_router.include_router(users_router)
admin_router.include_router(watch_folders_router)
admin_router.include_router(mcp_router)
admin_router.include_router(backup_router)
admin_router.include_router(config_router)
admin_router.include_router(queue_router)
admin_router.include_router(logs_router)
admin_router.include_router(stats_router)
admin_router.include_router(processing_router)
