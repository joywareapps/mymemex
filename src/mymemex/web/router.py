"""Web UI routes — server-rendered HTML pages for document management."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates

from ..services import NotFoundError
from ..services.document import DocumentService
from ..services.search import SearchService
from ..services.tag import TagService
from ..storage.database import get_session

import os

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["demo_mode"] = os.environ.get("DEMO_MODE") == "true"


@router.get("/")
async def document_list(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = None,
    tag: str | None = None,
    sort_by: str = "ingested_at",
    sort_order: str = "desc",
):
    """Document list / dashboard page."""
    async with get_session() as session:
        doc_service = DocumentService(session)
        tag_service = TagService(session)

        items, total = await doc_service.list_documents(
            page=page,
            per_page=per_page,
            status=status,
            tag=tag,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        all_tags = await tag_service.list_tags()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse(request, "index.html", {
        "documents": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "status_filter": status,
        "tag_filter": tag,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "tags": all_tags,
        "check_setup": True,
    })


@router.get("/document/{document_id}")
async def document_detail(request: Request, document_id: int):
    """Document detail page."""
    async with get_session() as session:
        doc_service = DocumentService(session)
        tag_service = TagService(session)

        try:
            doc = await doc_service.get_document(document_id)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Document not found")

        all_tags = await tag_service.list_tags()

    return templates.TemplateResponse(request, "document.html", {
        "doc": doc,
        "all_tags": all_tags,
    })


@router.get("/search")
async def search_page(
    request: Request,
    q: str | None = None,
    mode: str = "keyword",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Search results page."""
    results = []
    total = 0
    error = None

    if q:
        async with get_session() as session:
            config = request.app.state.config
            service = SearchService(session, config)

            if mode == "hybrid":
                try:
                    data = await service.hybrid_search(q, limit=per_page)
                    results = data["results"]
                    total = len(results)
                except Exception as e:
                    error = str(e)
            else:
                search_results, total = await service.keyword_search(q, page, per_page)
                results = search_results

    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1

    return templates.TemplateResponse(request, "search.html", {
        "query": q or "",
        "mode": mode,
        "results": results,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "error": error,
    })


@router.get("/tags")
async def tag_browser(request: Request):
    """Tag browser page."""
    async with get_session() as session:
        tag_service = TagService(session)
        tags = await tag_service.list_tags()

    return templates.TemplateResponse(request, "tags.html", {
        "tags": tags,
    })


@router.get("/upload")
async def upload_page(request: Request):
    """Upload interface page."""
    if os.environ.get("DEMO_MODE") == "true":
        raise HTTPException(status_code=403, detail="Uploads are disabled in demo mode")
    return templates.TemplateResponse(request, "upload.html")


# Admin pages
@router.get("/admin/setup")
async def admin_setup(request: Request):
    return templates.TemplateResponse(request, "admin/setup.html")


@router.get("/admin/settings")
async def admin_settings(request: Request):
    return templates.TemplateResponse(request, "admin/settings.html")


@router.get("/admin/watch-folders")
async def admin_watch_folders(request: Request):
    return templates.TemplateResponse(request, "admin/watch_folders.html")


@router.get("/admin/mcp")
async def admin_mcp(request: Request):
    return templates.TemplateResponse(request, "admin/mcp.html")


@router.get("/admin/backup")
async def admin_backup(request: Request):
    return templates.TemplateResponse(request, "admin/backup.html")


@router.get("/admin/users")
async def admin_users(request: Request):
    return templates.TemplateResponse(request, "admin/users.html")


@router.get("/admin/queue")
async def admin_queue(request: Request):
    return templates.TemplateResponse(request, "admin/queue.html")


@router.get("/admin/logs")
async def admin_logs(request: Request):
    return templates.TemplateResponse(request, "admin/logs.html")
