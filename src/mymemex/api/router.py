"""Main API router aggregating sub-routers."""

from fastapi import APIRouter

from .admin import admin_router
from .documents import router as documents_router
from .search import router as search_router
from .system import router as system_router
from .tags import router as tags_router

api_router = APIRouter()

api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(tags_router, prefix="/tags", tags=["tags"])
api_router.include_router(system_router, tags=["system"])
api_router.include_router(admin_router, prefix="/admin")
