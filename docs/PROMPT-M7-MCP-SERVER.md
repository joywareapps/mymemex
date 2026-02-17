# M7: MCP Server Implementation

**Goal:** Expose Librarian's capabilities via Model Context Protocol (MCP), enabling conversational access from Claude Desktop, OpenClaw, and any MCP-compatible client.

**Prerequisites:**
- ✅ M6.5 Service Layer complete (services ready to use)
- ✅ All 90 tests passing
- ✅ MCP spec documented in `docs/MCP-SPEC.md`

---

## Overview

Build an MCP server that exposes Librarian's document intelligence through 8 tools and 2 resources. MCP tools are thin wrappers around the service layer extracted in M6.5.

**Key principle:** No business logic in MCP handlers — delegate to services.

---

## Architecture

```
MCP Client (Claude Desktop / OpenClaw)
         │
         ▼
┌─────────────────────────────────────┐
│        MCP Server (M7)              │
│  ┌─────────────────────────────────┐│
│  │  Tool Handlers (thin wrappers)  ││
│  │  - search_documents             ││
│  │  - get_document                 ││
│  │  - get_document_text            ││
│  │  - list_documents               ││
│  │  - add_tag / remove_tag         ││
│  │  - upload_document              ││
│  │  - get_library_stats            ││
│  └─────────────────────────────────┘│
│                │                     │
│                ▼                     │
│  ┌─────────────────────────────────┐│
│  │     Service Layer (M6.5)        ││
│  │  SearchService                  ││
│  │  DocumentService                ││
│  │  TagService                     ││
│  │  IngestService                  ││
│  │  StatsService                   ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Install MCP SDK

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0.0"]
```

Or add directly:
```bash
pip install mcp
```

---

### Step 2: Create MCP Server Structure

```
src/librarian/mcp/
├── __init__.py
├── server.py          # Main MCP server setup
├── tools/
│   ├── __init__.py
│   ├── search.py      # search_documents tool
│   ├── documents.py   # get_document, get_document_text, list_documents
│   ├── tags.py        # add_tag, remove_tag
│   ├── upload.py      # upload_document
│   └── stats.py       # get_library_stats
├── resources/
│   ├── __init__.py
│   ├── tags.py        # library://tags resource
│   └── stats.py       # library://stats resource
└── prompts/
    ├── __init__.py
    └── templates.py   # search_and_summarize, compare_documents
```

---

### Step 3: Main MCP Server (`server.py`)

```python
"""
Librarian MCP Server

Exposes document intelligence via Model Context Protocol.
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server

from librarian.core.config import Config
from librarian.services import (
    SearchService,
    DocumentService,
    TagService,
    IngestService,
    StatsService,
)

# Create MCP server instance
app = Server("librarian")

# Initialize services (shared across tools)
_config = Config.load()
_services = {
    "search": SearchService(session_factory=_get_session, config=_config),
    "document": DocumentService(session_factory=_get_session, config=_config),
    "tag": TagService(session_factory=_get_session, config=_config),
    "ingest": IngestService(session_factory=_get_session, config=_config),
    "stats": StatsService(session_factory=_get_session, config=_config),
}

# Register tools
from librarian.mcp.tools import register_all_tools
register_all_tools(app, _services)

# Register resources
from librarian.mcp.resources import register_all_resources
register_all_resources(app, _services)

# Register prompts
from librarian.mcp.prompts import register_all_prompts
register_all_prompts(app)


def _get_session():
    """Database session factory for services."""
    from librarian.core.database import SessionLocal
    return SessionLocal()


async def run_stdio():
    """Run MCP server with stdio transport (Claude Desktop)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main():
    """Entry point for `librarian mcp serve` command."""
    import asyncio
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
```

---

### Step 4: Implement MCP Tools

#### Tool: `search_documents`

```python
# src/librarian/mcp/tools/search.py

from mcp.server import Server
from mcp.types import Tool, TextContent

from librarian.services import SearchService


def register_search_tools(app: Server, services: dict):
    """Register search-related MCP tools."""

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="search_documents",
                description="Search the document library using keyword, semantic, or hybrid search.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["keyword", "semantic", "hybrid"],
                            "default": "hybrid",
                            "description": "Search mode"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum results to return"
                        },
                        "filters": {
                            "type": "object",
                            "properties": {
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "date_from": {"type": "string"},
                                "date_to": {"type": "string"}
                            }
                        }
                    },
                    "required": ["query"]
                }
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "search_documents":
            search: SearchService = services["search"]

            # Extract parameters
            query = arguments["query"]
            mode = arguments.get("mode", "hybrid")
            limit = arguments.get("limit", 10)
            filters = arguments.get("filters", {})

            # Call service
            try:
                results = await search.search(
                    query=query,
                    mode=mode,
                    limit=limit,
                    filters=filters
                )

                # Format response
                return [TextContent(
                    type="text",
                    text=_format_search_results(results)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"Error [SEARCH_FAILED]: {str(e)}"
                )]


def _format_search_results(results) -> str:
    """Format search results for MCP response."""
    lines = [f"Found {len(results)} documents:\n"]

    for r in results:
        lines.append(f"**{r.title}** (score: {r.score:.2f})")
        lines.append(f"  ID: {r.document_id}")
        lines.append(f"  Tags: {', '.join(r.tags)}")
        lines.append(f"  Snippet: {r.text[:200]}...")
        lines.append("")

    return "\n".join(lines)
```

#### Tool: `get_document`

```python
# src/librarian/mcp/tools/documents.py

from mcp.server import Server
from mcp.types import Tool, TextContent

from librarian.services import DocumentService
from librarian.services.exceptions import NotFoundError


def register_document_tools(app: Server, services: dict):
    """Register document-related MCP tools."""

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="get_document",
                description="Retrieve full document metadata and content chunks.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "integer",
                            "description": "Document ID"
                        }
                    },
                    "required": ["document_id"]
                }
            ),
            Tool(
                name="get_document_text",
                description="Retrieve extracted text for a specific page range. Useful for LLMs with context limits.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "integer",
                            "description": "Document ID"
                        },
                        "page_start": {
                            "type": "integer",
                            "description": "Starting page (1-indexed)",
                            "default": 1
                        },
                        "page_end": {
                            "type": "integer",
                            "description": "Ending page (inclusive)"
                        }
                    },
                    "required": ["document_id"]
                }
            ),
            Tool(
                name="list_documents",
                description="Paginated list of documents with optional filters.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "maximum": 100
                        },
                        "offset": {
                            "type": "integer",
                            "default": 0
                        },
                        "sort": {
                            "type": "string",
                            "enum": ["created_desc", "created_asc", "title"],
                            "default": "created_desc"
                        },
                        "filters": {
                            "type": "object",
                            "properties": {
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "status": {"type": "string"},
                                "has_ocr": {"type": "boolean"}
                            }
                        }
                    }
                }
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        doc_service: DocumentService = services["document"]

        try:
            if name == "get_document":
                doc_id = arguments["document_id"]
                doc = await doc_service.get(doc_id)
                if not doc:
                    raise NotFoundError(f"Document {doc_id} not found")

                return [TextContent(
                    type="text",
                    text=_format_document(doc)
                )]

            elif name == "get_document_text":
                doc_id = arguments["document_id"]
                page_start = arguments.get("page_start", 1)
                page_end = arguments.get("page_end")

                text = await doc_service.get_text(
                    document_id=doc_id,
                    page_start=page_start,
                    page_end=page_end
                )

                return [TextContent(
                    type="text",
                    text=text
                )]

            elif name == "list_documents":
                limit = min(arguments.get("limit", 50), 100)
                offset = arguments.get("offset", 0)
                sort = arguments.get("sort", "created_desc")
                filters = arguments.get("filters", {})

                docs = await doc_service.list(
                    limit=limit,
                    offset=offset,
                    sort=sort,
                    filters=filters
                )

                return [TextContent(
                    type="text",
                    text=_format_document_list(docs)
                )]

        except NotFoundError as e:
            return [TextContent(
                type="text",
                text=f"Error [DOCUMENT_NOT_FOUND]: {str(e)}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error [INTERNAL_ERROR]: {str(e)}"
            )]


def _format_document(doc) -> str:
    """Format document for MCP response."""
    lines = [
        f"# {doc.title}",
        f"",
        f"**ID:** {doc.id}",
        f"**File:** {doc.original_filename}",
        f"**Pages:** {doc.page_count}",
        f"**Status:** {doc.status}",
        f"**Tags:** {', '.join(doc.tags)}",
        f"",
        "## Content",
        ""
    ]

    for chunk in doc.chunks[:5]:  # Limit chunks to avoid huge responses
        lines.append(f"[Page {chunk.page_number}]")
        lines.append(chunk.text[:500])
        lines.append("")

    if len(doc.chunks) > 5:
        lines.append(f"... and {len(doc.chunks) - 5} more chunks")

    return "\n".join(lines)


def _format_document_list(docs) -> str:
    """Format document list for MCP response."""
    lines = [f"Documents ({len(docs)}):\n"]

    for doc in docs:
        lines.append(f"- **{doc.title}** (ID: {doc.id}, {doc.page_count} pages)")
        if doc.tags:
            lines.append(f"  Tags: {', '.join(doc.tags)}")

    return "\n".join(lines)
```

#### Tool: `add_tag` / `remove_tag`

```python
# src/librarian/mcp/tools/tags.py

from mcp.server import Server
from mcp.types import Tool, TextContent

from librarian.services import TagService
from librarian.services.exceptions import NotFoundError


def register_tag_tools(app: Server, services: dict):
    """Register tag-related MCP tools."""

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="add_tag",
                description="Add a tag to a document.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer"},
                        "tag": {"type": "string"}
                    },
                    "required": ["document_id", "tag"]
                }
            ),
            Tool(
                name="remove_tag",
                description="Remove a tag from a document.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer"},
                        "tag": {"type": "string"}
                    },
                    "required": ["document_id", "tag"]
                }
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        tag_service: TagService = services["tag"]

        try:
            doc_id = arguments["document_id"]
            tag = arguments["tag"]

            if name == "add_tag":
                success = await tag_service.add_to_document(doc_id, tag)
                return [TextContent(
                    type="text",
                    text=f"Added tag '{tag}' to document {doc_id}"
                )]

            elif name == "remove_tag":
                success = await tag_service.remove_from_document(doc_id, tag)
                return [TextContent(
                    type="text",
                    text=f"Removed tag '{tag}' from document {doc_id}"
                )]

        except NotFoundError as e:
            return [TextContent(
                type="text",
                text=f"Error [NOT_FOUND]: {str(e)}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error [INTERNAL_ERROR]: {str(e)}"
            )]
```

#### Tool: `upload_document`

```python
# src/librarian/mcp/tools/upload.py

from mcp.server import Server
from mcp.types import Tool, TextContent

from librarian.services import IngestService


def register_upload_tools(app: Server, services: dict):
    """Register upload MCP tool."""

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="upload_document",
                description="Upload a new document to the library. Prefer file_path for local files. Use base64 content only for small files (<5MB).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename (e.g., 'invoice.pdf')"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Local file path (PREFERRED)"
                        },
                        "content": {
                            "type": "string",
                            "description": "Base64-encoded file content (fallback, max 5MB)"
                        }
                    },
                    "required": ["filename"]
                }
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        ingest: IngestService = services["ingest"]

        try:
            filename = arguments["filename"]
            file_path = arguments.get("file_path")
            content_b64 = arguments.get("content")

            # Validate: exactly one of file_path or content
            if not file_path and not content_b64:
                return [TextContent(
                    type="text",
                    text="Error [INVALID_PARAMETERS]: Provide either file_path or content"
                )]

            if file_path and content_b64:
                return [TextContent(
                    type="text",
                    text="Error [INVALID_PARAMETERS]: Provide only one of file_path or content, not both"
                )]

            # Upload via service
            result = await ingest.upload(
                filename=filename,
                file_path=file_path,
                content_b64=content_b64
            )

            return [TextContent(
                type="text",
                text=f"Document uploaded successfully!\n"
                     f"Filename: {result.filename}\n"
                     f"Inbox path: {result.inbox_path}\n"
                     f"Status: Queued for processing"
            )]

        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error [UPLOAD_FAILED]: {str(e)}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error [INTERNAL_ERROR]: {str(e)}"
            )]
```

#### Tool: `get_library_stats`

```python
# src/librarian/mcp/tools/stats.py

from mcp.server import Server
from mcp.types import Tool, TextContent

from librarian.services import StatsService


def register_stats_tools(app: Server, services: dict):
    """Register stats MCP tool."""

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="get_library_stats",
                description="Get overall library statistics.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        stats: StatsService = services["stats"]

        try:
            library_stats = await stats.get_library_stats()

            return [TextContent(
                type="text",
                text=_format_stats(library_stats)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error [INTERNAL_ERROR]: {str(e)}"
            )]


def _format_stats(stats) -> str:
    """Format library stats for MCP response."""
    return f"""# Library Statistics

## Documents
- Total: {stats.documents.total}
- Processed: {stats.documents.processed}
- Pending: {stats.documents.pending}
- Error: {stats.documents.error}

## Storage
- Total: {stats.storage.total_mb:.1f} MB

## Chunks
- Total: {stats.chunks.total}
- With embeddings: {stats.chunks.with_embeddings}

## Top Tags
{chr(10).join(f"- {t.name}: {t.count}" for t in stats.tags.top_tags[:10])}
"""
```

---

### Step 5: Implement MCP Resources

```python
# src/librarian/mcp/resources/tags.py

from mcp.server import Server
from mcp.types import Resource

from librarian.services import StatsService


def register_tag_resources(app: Server, services: dict):
    """Register library://tags resource."""

    @app.list_resources()
    async def list_resources():
        return [
            Resource(
                uri="library://tags",
                name="All Tags",
                description="List of all tags with document counts",
                mimeType="application/json"
            )
        ]

    @app.read_resource()
    async def read_resource(uri: str):
        if uri == "library://tags":
            stats: StatsService = services["stats"]
            tag_stats = await stats.get_tag_stats()

            import json
            return json.dumps([
                {"name": t.name, "count": t.count}
                for t in tag_stats
            ])
```

```python
# src/librarian/mcp/resources/stats.py

from mcp.server import Server
from mcp.types import Resource

from librarian.services import StatsService


def register_stats_resources(app: Server, services: dict):
    """Register library://stats resource."""

    @app.list_resources()
    async def list_resources():
        return [
            Resource(
                uri="library://stats",
                name="Library Statistics",
                description="Overall library statistics",
                mimeType="application/json"
            )
        ]

    @app.read_resource()
    async def read_resource(uri: str):
        if uri == "library://stats":
            stats: StatsService = services["stats"]
            library_stats = await stats.get_library_stats()

            import json
            from dataclasses import asdict
            return json.dumps(asdict(library_stats))
```

---

### Step 6: Implement MCP Prompts

```python
# src/librarian/mcp/prompts/templates.py

from mcp.server import Server
from mcp.types import Prompt


def register_all_prompts(app: Server):
    """Register MCP prompts."""

    @app.list_prompts()
    async def list_prompts():
        return [
            Prompt(
                name="search_and_summarize",
                description="Search the library and summarize key findings",
                arguments=[
                    {"name": "query", "description": "Search query", "required": True}
                ]
            ),
            Prompt(
                name="compare_documents",
                description="Compare two or more documents",
                arguments=[
                    {"name": "document_ids", "description": "Comma-separated document IDs", "required": True}
                ]
            )
        ]

    @app.get_prompt()
    async def get_prompt(name: str, arguments: dict):
        if name == "search_and_summarize":
            query = arguments.get("query", "")
            return f"""Search the library for "{query}" and summarize the key findings.

Focus on:
- Main topics covered
- Document types found
- Any notable patterns or outliers

Cite specific documents when relevant."""

        elif name == "compare_documents":
            doc_ids = arguments.get("document_ids", "")
            return f"""Compare the following documents:
- Document IDs: {doc_ids}

Analyze:
- Key similarities
- Important differences
- Temporal changes (if applicable)
- Recommendations"""
```

---

### Step 7: CLI Integration

Add MCP command to CLI (`src/librarian/cli.py`):

```python
import typer

app = typer.Typer()

@app.command()
def serve():
    """Start Librarian REST API server."""
    import uvicorn
    from librarian.api.main import create_app
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)

@app.command()
def mcp():
    """Start Librarian MCP server (stdio transport)."""
    from librarian.mcp.server import main
    main()

if __name__ == "__main__":
    app()
```

**Usage:**
```bash
# Start MCP server for Claude Desktop
librarian mcp

# Start REST API
librarian serve
```

---

### Step 8: Claude Desktop Configuration

User adds to Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "librarian": {
      "command": "librarian",
      "args": ["mcp"]
    }
  }
}
```

---

### Step 9: HTTP/SSE Transport (Optional - Phase 2)

For OpenClaw integration, add HTTP transport:

```python
# src/librarian/mcp/http_transport.py

from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route


def create_http_app():
    """Create Starlette app with SSE transport."""
    from librarian.mcp.server import app as mcp_server

    sse = SseServerTransport("/messages")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )

    async def handle_messages(request):
        await sse.handle_post_message(request._receive, request._send)

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"])
        ]
    )
```

---

## Testing

### Unit Tests

Create `tests/test_mcp_tools.py`:

```python
import pytest
from librarian.mcp.tools.search import _format_search_results
from librarian.mcp.tools.documents import _format_document


def test_format_search_results():
    # Mock results
    results = [...]
    formatted = _format_search_results(results)
    assert "Found" in formatted


def test_format_document():
    # Mock document
    doc = ...
    formatted = _format_document(doc)
    assert doc.title in formatted
```

### Integration Test

```python
@pytest.mark.asyncio
async def test_search_documents_tool():
    """Test search_documents MCP tool."""
    from librarian.mcp.tools.search import call_tool

    result = await call_tool("search_documents", {"query": "test", "limit": 5})

    assert len(result) == 1
    assert result[0].type == "text"
```

### Manual Test

```bash
# Start MCP server
librarian mcp

# In another terminal, test with MCP CLI tool
mcp test librarian
```

---

## Success Criteria

1. ✅ MCP server starts with `librarian mcp`
2. ✅ All 8 tools registered and callable
3. ✅ Claude Desktop can connect and use tools
4. ✅ Tools delegate to services (no duplicate logic)
5. ✅ Error handling follows MCP protocol
6. ✅ All existing tests still pass
7. ✅ Security: path validation, upload limits

---

## Time Estimate

- MCP server structure: 2-3 hours
- 8 tool implementations: 6-8 hours
- 2 resource implementations: 1-2 hours
- 2 prompt templates: 1 hour
- CLI integration: 1 hour
- Testing: 2-3 hours
- Documentation: 1 hour

**Total: 14-19 hours (1.5-2 weeks)**

---

## References

- `docs/MCP-SPEC.md` — Full MCP specification
- `docs/ARCHITECTURE.md` — ADR-007 (MCP-First Interface)
- `src/librarian/services/` — Service layer (M6.5)
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
