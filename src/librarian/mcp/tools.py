"""MCP tool handlers — thin wrappers around the service layer."""

from __future__ import annotations

import base64
import json

from mcp.server.fastmcp import Context, FastMCP

from ..services import (
    NotFoundError,
    ServiceError,
    ServiceUnavailableError,
)
from ..storage.database import get_session
from .server import LibrarianContext


def _get_ctx(ctx: Context) -> LibrarianContext:
    return ctx.request_context.lifespan_context


def register(mcp: FastMCP) -> None:
    """Register all MCP tools."""

    @mcp.tool()
    async def search_documents(
        query: str,
        mode: str = "hybrid",
        limit: int = 10,
        ctx: Context = None,
    ) -> str:
        """Search the document library using keyword, semantic, or hybrid search.

        Args:
            query: The search query.
            mode: Search mode — keyword, semantic, or hybrid (default: hybrid).
            limit: Maximum results to return (default: 10).
        """
        lctx = _get_ctx(ctx)
        try:
            async with get_session() as session:
                from ..services.search import SearchService

                service = SearchService(session, lctx.config)

                if mode == "keyword":
                    results, total = await service.keyword_search(query, page=1, per_page=limit)
                    return _format_keyword_results(results, total, query, mode)
                elif mode == "semantic":
                    results = await service.semantic_search(query, limit=limit)
                    return _format_semantic_results(results, query, mode)
                else:
                    data = await service.hybrid_search(query, limit=limit)
                    return _format_hybrid_results(data, query)
        except ServiceUnavailableError as e:
            raise ValueError(f"[SEARCH_UNAVAILABLE] {e}")
        except ServiceError as e:
            raise ValueError(f"[SEARCH_FAILED] {e}")

    @mcp.tool()
    async def get_document(document_id: int, ctx: Context = None) -> str:
        """Retrieve full document metadata and content chunks.

        Args:
            document_id: The document ID.
        """
        try:
            async with get_session() as session:
                from ..services.document import DocumentService

                service = DocumentService(session)
                data = await service.get_document(document_id)
                return _format_document(data)
        except NotFoundError:
            raise ValueError(f"[DOCUMENT_NOT_FOUND] Document {document_id} not found")

    @mcp.tool()
    async def get_document_text(
        document_id: int,
        page_start: int = 1,
        page_end: int | None = None,
        ctx: Context = None,
    ) -> str:
        """Retrieve extracted text for a specific page range.

        Useful for LLMs with context limits — request specific pages instead of full doc.

        Args:
            document_id: The document ID.
            page_start: Starting page (1-indexed, default: 1).
            page_end: Ending page (inclusive, default: last page).
        """
        try:
            async with get_session() as session:
                from ..services.document import DocumentService

                service = DocumentService(session)
                data = await service.get_document_text(
                    document_id, page_start=page_start, page_end=page_end
                )
                return _format_document_text(data)
        except NotFoundError:
            raise ValueError(f"[DOCUMENT_NOT_FOUND] Document {document_id} not found")

    @mcp.tool()
    async def list_documents(
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        sort: str = "created_desc",
        ctx: Context = None,
    ) -> str:
        """List documents with optional filters and pagination.

        Args:
            limit: Maximum results (default: 50, max: 100).
            offset: Number of results to skip (default: 0).
            status: Filter by status (pending, processing, processed, error).
            category: Filter by category.
            tag: Filter by tag name.
            sort: Sort order — created_desc, created_asc, or title (default: created_desc).
        """
        limit = min(limit, 100)

        # Convert offset/limit to page/per_page
        page = (offset // limit) + 1 if limit > 0 else 1

        # Map sort names
        sort_map = {
            "created_desc": ("ingested_at", "desc"),
            "created_asc": ("ingested_at", "asc"),
            "title": ("title", "asc"),
        }
        sort_by, sort_order = sort_map.get(sort, ("ingested_at", "desc"))

        async with get_session() as session:
            from ..services.document import DocumentService

            service = DocumentService(session)
            items, total = await service.list_documents(
                page=page,
                per_page=limit,
                status=status,
                category=category,
                tag=tag,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return _format_document_list(items, total, limit, offset)

    @mcp.tool()
    async def add_tag(document_id: int, tag: str, ctx: Context = None) -> str:
        """Add a tag to a document.

        Args:
            document_id: The document ID.
            tag: Tag name to add.
        """
        try:
            async with get_session() as session:
                from ..services.tag import TagService

                service = TagService(session)
                result = await service.add_tag_to_document(document_id, tag)
                status = "added" if result["is_new"] else "already present"
                return f"Tag '{tag}' {status} on document {document_id}."
        except NotFoundError as e:
            raise ValueError(f"[DOCUMENT_NOT_FOUND] {e}")

    @mcp.tool()
    async def remove_tag(document_id: int, tag: str, ctx: Context = None) -> str:
        """Remove a tag from a document.

        Args:
            document_id: The document ID.
            tag: Tag name to remove.
        """
        try:
            async with get_session() as session:
                from ..services.tag import TagService

                service = TagService(session)
                await service.remove_tag_from_document(document_id, tag)
                return f"Tag '{tag}' removed from document {document_id}."
        except NotFoundError as e:
            raise ValueError(f"[TAG_NOT_FOUND] {e}")

    @mcp.tool()
    async def upload_document(
        filename: str,
        file_path: str | None = None,
        content: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Upload a document to the library.

        Provide either file_path (preferred for local files) or base64 content.

        Args:
            filename: Filename (e.g., 'invoice.pdf').
            file_path: Local file path (preferred).
            content: Base64-encoded file content (fallback, max 5MB).
        """
        lctx = _get_ctx(ctx)

        if not file_path and not content:
            raise ValueError("[INVALID_PARAMETERS] Provide either file_path or content")
        if file_path and content:
            raise ValueError(
                "[INVALID_PARAMETERS] Provide only one of file_path or content, not both"
            )

        try:
            async with get_session() as session:
                from ..services.ingest import IngestService

                service = IngestService(session, lctx.config)

                if file_path:
                    allowed = (
                        lctx.config.mcp.security.allowed_parent_paths
                        or lctx.config.watch.directories
                    )
                    result = await service.upload_from_path(
                        file_path, filename, allowed_paths=allowed
                    )
                else:
                    # Decode base64 content
                    try:
                        raw = base64.b64decode(content)
                    except Exception:
                        raise ValueError("[INVALID_PARAMETERS] Invalid base64 content")

                    max_bytes = lctx.config.mcp.security.max_upload_size_mb * 1024 * 1024
                    if len(raw) > max_bytes:
                        raise ValueError(
                            f"[UPLOAD_TOO_LARGE] File exceeds "
                            f"{lctx.config.mcp.security.max_upload_size_mb}MB limit"
                        )

                    result = await service.upload(raw, filename)
                    result = {
                        "filename": filename,
                        "inbox_path": result["path"],
                        "size": result["size"],
                    }

                return (
                    f"Document uploaded successfully.\n"
                    f"Filename: {result['filename']}\n"
                    f"Inbox path: {result['inbox_path']}\n"
                    f"Size: {result['size']} bytes\n"
                    f"Status: Queued for processing"
                )
        except ValueError:
            raise
        except ServiceError as e:
            raise ValueError(f"[UPLOAD_FAILED] {e}")

    @mcp.tool()
    async def get_library_stats(ctx: Context = None) -> str:
        """Get overall library statistics — document counts, storage, and queue status."""
        lctx = _get_ctx(ctx)
        async with get_session() as session:
            from ..services.stats import StatsService

            service = StatsService(session, lctx.config)
            stats = await service.get_library_stats()
            return _format_stats(stats)


# --- Formatting helpers ---


def _format_keyword_results(results: list[dict], total: int, query: str, mode: str) -> str:
    lines = [f"Found {total} results for '{query}' ({mode} search):\n"]
    for r in results:
        lines.append(f"- **{r.get('title') or r['original_filename']}** (ID: {r['document_id']})")
        if r.get("page_number"):
            lines.append(f"  Page: {r['page_number']}")
        lines.append(f"  Snippet: {r['snippet'][:200]}")
        if r.get("tags"):
            lines.append(f"  Tags: {', '.join(r['tags'])}")
        lines.append("")
    return "\n".join(lines)


def _format_semantic_results(results: list[dict], query: str, mode: str) -> str:
    lines = [f"Found {len(results)} results for '{query}' ({mode} search):\n"]
    for r in results:
        title = r.get("title") or r.get("original_filename") or f"Chunk {r['chunk_id']}"
        lines.append(f"- **{title}** (ID: {r['document_id']}, distance: {r['distance']:.3f})")
        lines.append(f"  {r['text'][:200]}")
        if r.get("tags"):
            lines.append(f"  Tags: {', '.join(r['tags'])}")
        lines.append("")
    return "\n".join(lines)


def _format_hybrid_results(data: dict, query: str) -> str:
    results = data["results"]
    lines = [
        f"Found {len(results)} results for '{query}' (hybrid search):",
        f"  Keyword matches: {data['keyword_count']}, Semantic matches: {data['semantic_count']}\n",
    ]
    for r in results:
        title = r.get("title") or r.get("original_filename") or f"Chunk {r['chunk_id']}"
        lines.append(f"- **{title}** (ID: {r['document_id']}, score: {r['score']:.4f})")
        if r.get("text"):
            lines.append(f"  {r['text'][:200]}")
        if r.get("tags"):
            lines.append(f"  Tags: {', '.join(r['tags'])}")
        lines.append("")
    return "\n".join(lines)


def _format_document(data: dict) -> str:
    lines = [
        f"# {data.get('title') or data['original_filename']}",
        "",
        f"**ID:** {data['id']}",
        f"**File:** {data['original_filename']}",
        f"**Path:** {data['original_path']}",
        f"**Size:** {data['file_size']} bytes",
        f"**Pages:** {data.get('page_count') or 'N/A'}",
        f"**Status:** {data['status']}",
        f"**Category:** {data.get('category') or 'N/A'}",
        f"**Tags:** {', '.join(data.get('tags', [])) or 'none'}",
        f"**Ingested:** {data['ingested_at']}",
        "",
    ]

    chunks = data.get("chunks", [])
    if chunks:
        lines.append("## Content")
        lines.append("")
        for c in chunks[:10]:
            page = c.get("page_number")
            prefix = f"[Page {page}] " if page else ""
            lines.append(f"{prefix}{c['text'][:500]}")
            lines.append("")
        if len(chunks) > 10:
            lines.append(f"... and {len(chunks) - 10} more chunks")

    return "\n".join(lines)


def _format_document_text(data: dict) -> str:
    lines = [
        f"# {data.get('title') or 'Untitled'}",
        f"Pages {data['page_start']}-{data['page_end']} of {data['total_pages']}",
        "",
        data["text"],
    ]
    return "\n".join(lines)


def _format_document_list(items: list[dict], total: int, limit: int, offset: int) -> str:
    lines = [f"Documents ({total} total, showing {offset + 1}-{offset + len(items)}):\n"]
    for d in items:
        title = d.get("title") or d["original_filename"]
        lines.append(f"- **{title}** (ID: {d['id']}, {d.get('page_count') or '?'} pages)")
        lines.append(f"  Status: {d['status']}, Size: {d['file_size']} bytes")
        if d.get("tags"):
            lines.append(f"  Tags: {', '.join(d['tags'])}")
        lines.append("")
    return "\n".join(lines)


def _format_stats(stats: dict) -> str:
    doc_stats = stats["doc_stats"]
    by_status = doc_stats.get("by_status", {})

    lines = [
        "# Library Statistics",
        "",
        "## Documents",
        f"- Total: {doc_stats['total']}",
        f"- Processed: {by_status.get('processed', 0)}",
        f"- Pending: {by_status.get('pending', 0)}",
        f"- Error: {by_status.get('error', 0)}",
        "",
        "## Storage",
        f"- SQLite size: {stats['sqlite_size_mb']:.1f} MB",
        "",
        "## Chunks",
        f"- Total: {stats['total_chunks']}",
        "",
        "## Queue",
    ]

    queue = stats.get("queue_stats", {})
    for key, val in queue.items():
        lines.append(f"- {key}: {val}")

    return "\n".join(lines)
