# Librarian MCP Specification

**Version:** 1.1
**Last Updated:** 2026-02-17

This document specifies the Model Context Protocol (MCP) interface for Librarian.

---

## Overview

Librarian exposes its document intelligence capabilities via MCP, enabling integration with:
- **Claude Desktop** — Local AI assistant
- **OpenClaw** — Your personal AI assistant
- **Any MCP-compatible client**

### Transport Options

| Transport | Use Case | Port |
|-----------|----------|------|
| `stdio` | Local integration (Claude Desktop) | N/A |
| `HTTP/SSE` | Remote access (OpenClaw, web) | 8001 (localhost only by default) |

---

## MCP Tools

### `search_documents`

Search the document library using keyword, semantic, or hybrid search.

**Parameters:**
```json
{
  "query": "string — The search query",
  "mode": "keyword | semantic | hybrid — default: hybrid",
  "limit": "integer — max results, default: 10",
  "filters": {
    "tags": ["string"] — filter by tags (optional),
    "date_from": "ISO date string (optional)",
    "date_to": "ISO date string (optional)"
  }
}
```

**Returns:**
```json
{
  "results": [
    {
      "document_id": 123,
      "chunk_id": 456,
      "title": "Document Title",
      "text": "Matching text snippet...",
      "page_number": 1,
      "score": 0.85,
      "tags": ["insurance", "policy"],
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 42,
  "query": "original query",
  "mode": "hybrid"
}
```

---

### `get_document`

Retrieve full document metadata and content chunks.

**Parameters:**
```json
{
  "document_id": "integer — required"
}
```

**Returns:**
```json
{
  "id": 123,
  "title": "Document Title",
  "original_filename": "scan_001.pdf",
  "file_path": "/watched/scans/scan_001.pdf",
  "file_size": 1024000,
  "file_hash": "sha256:abc123...",
  "page_count": 5,
  "status": "processed",
  "extraction_method": "native | ocr",
  "created_at": "2024-01-15T10:30:00Z",
  "tags": ["insurance", "policy"],
  "chunks": [
    {
      "id": 456,
      "page_number": 1,
      "text": "First chunk of text...",
      "extraction_method": "native"
    }
  ]
}
```

---

### `get_document_text`

Retrieve extracted text for a specific page range. Designed for LLM workflows where loading the full document exceeds context limits.

**Parameters:**
```json
{
  "document_id": "integer — required",
  "page_start": "integer — optional, 1-indexed, default: 1",
  "page_end": "integer — optional, inclusive, default: last page"
}
```

**Returns:**
```json
{
  "document_id": 123,
  "title": "Document Title",
  "text": "Concatenated text for the requested page range...",
  "pages": [
    {"number": 1, "text": "Page 1 extracted text..."},
    {"number": 2, "text": "Page 2 extracted text..."}
  ],
  "total_pages": 5,
  "page_start": 1,
  "page_end": 2
}
```

**Notes:**
- If `page_start` / `page_end` are omitted, returns all pages
- `text` field contains concatenated text for convenience; `pages` array provides per-page access
- Useful for summarizing specific sections or extracting data from known pages

---

### `list_documents`

Paginated list of documents with optional filters.

**Parameters:**
```json
{
  "limit": "integer — default: 50, max: 100",
  "offset": "integer — default: 0",
  "sort": "created_desc | created_asc | title | relevance",
  "filters": {
    "tags": ["string"],
    "status": "pending | processing | processed | error",
    "has_ocr": "boolean"
  }
}
```

**Returns:**
```json
{
  "documents": [
    {
      "id": 123,
      "title": "Document Title",
      "original_filename": "file.pdf",
      "page_count": 5,
      "status": "processed",
      "tags": ["tag1"],
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 142,
  "limit": 50,
  "offset": 0
}
```

---

### `add_tag`

Add a tag to a document.

**Parameters:**
```json
{
  "document_id": "integer — required",
  "tag": "string — tag name, required"
}
```

**Returns:**
```json
{
  "success": true,
  "document_id": 123,
  "tag": "insurance",
  "is_new": true
}
```

---

### `remove_tag`

Remove a tag from a document.

**Parameters:**
```json
{
  "document_id": "integer — required",
  "tag": "string — tag name, required"
}
```

**Returns:**
```json
{
  "success": true,
  "document_id": 123,
  "tag": "insurance"
}
```

---

### `upload_document`

Upload a new document to the library. The document is placed in the inbox folder and picked up by the file watcher.

**Primary method (stdio transport):** Provide a `file_path` to a local file. This avoids base64 overhead and MCP message size limits.

**Fallback method:** Provide base64-encoded `content` for small files only (max 5 MB before encoding, configurable via `max_upload_size_mb`).

**Parameters:**
```json
{
  "filename": "string — required, e.g., 'invoice.pdf'",
  "file_path": "string — local file path (PREFERRED for stdio transport)",
  "content": "string — base64-encoded file content (fallback, max 5MB)"
}
```

**Returns:**
```json
{
  "success": true,
  "filename": "invoice.pdf",
  "inbox_path": "/watched/inbox/invoice.pdf",
  "message": "Document queued for processing"
}
```

**Notes:**
- Exactly one of `file_path` or `content` must be provided
- `file_path` is validated against `allowed_parent_paths` (see Security section)
- Base64 `content` is rejected if decoded size exceeds `max_upload_size_mb` (default: 5)
- For HTTP transport, use the REST API upload endpoint (`POST /api/v1/documents/upload`) for large files, then reference the document via MCP tools
- Document is not immediately available — processing takes a few seconds
- Use `list_documents` with `status: "processing"` to check progress

---

### `get_library_stats`

Get overall library statistics.

**Parameters:** None

**Returns:**
```json
{
  "documents": {
    "total": 142,
    "processed": 138,
    "pending": 2,
    "error": 2
  },
  "storage": {
    "total_bytes": 524288000,
    "total_mb": 500
  },
  "chunks": {
    "total": 2847,
    "with_embeddings": 2800
  },
  "tags": {
    "total": 24,
    "top_tags": [
      {"name": "insurance", "count": 45},
      {"name": "medical", "count": 32},
      {"name": "financial", "count": 28}
    ]
  },
  "processing": {
    "native_extraction": 85,
    "ocr_required": 15
  }
}
```

---

### `watch_directory`

Add a new directory to the watch list.

**Security:** This tool validates paths against `allowed_parent_paths` in config. It rejects any path outside the allowed boundaries to prevent exposure of sensitive system files. Consider making this admin-only in production deployments.

**Parameters:**
```json
{
  "path": "string — absolute path to directory",
  "recursive": "boolean — default: true"
}
```

**Returns:**
```json
{
  "success": true,
  "path": "/home/user/new-docs",
  "recursive": true,
  "existing_files": 12
}
```

**Validation:**
- Path must be absolute
- Path must exist and be a directory
- Path must be under one of the configured `allowed_parent_paths`
- Symlinks are resolved before validation (no symlink escapes)

---

## MCP Resources

Resources provide contextual data that MCP clients can use to understand the library state. Resources are kept lean — use tools for detailed data retrieval.

### `library://tags`

List all tags with counts. Useful for clients to offer tag-based filtering suggestions.

**Template:** `library://tags`

**Returns:**
```json
{
  "tags": [
    {"name": "insurance", "count": 45},
    {"name": "medical", "count": 32},
    {"name": "financial", "count": 28}
  ]
}
```

---

### `library://stats`

Library overview statistics. Same data as `get_library_stats` tool.

**Template:** `library://stats`

---

**Removed resources (rationale):**
- `library://documents` — Removed because listing all documents can be very large and MCP resources should be lightweight. Use the `list_documents` tool with pagination instead.
- `library://document/{id}` — Removed because per-document detail is better served by the `get_document` and `get_document_text` tools, which support pagination and page ranges.

---

## MCP Prompts

### `search_and_summarize`

Search for documents and provide a summary of results.

**Template:**
```
Search the library for "{query}" and summarize the key findings.

Focus on:
- Main topics covered
- Document types found
- Any notable patterns or outliers

Cite specific documents when relevant.
```

---

### `compare_documents`

Compare two or more documents.

**Template:**
```
Compare the following documents:
- Document IDs: {document_ids}

Analyze:
- Key similarities
- Important differences
- Temporal changes (if applicable)
- Recommendations
```

---

## Error Handling

All tools follow the MCP protocol error format. Errors are returned as tool results with `isError: true`, NOT as HTTP status codes.

**MCP error response format:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Error [DOCUMENT_NOT_FOUND]: Document with ID 999 not found"
    }
  ],
  "isError": true
}
```

**Error Codes** (included in error message text for debugging):

| Code | Description |
|------|-------------|
| `DOCUMENT_NOT_FOUND` | Invalid document ID |
| `INVALID_PARAMETERS` | Missing or invalid parameters |
| `SEARCH_UNAVAILABLE` | Search backend (Ollama) unavailable |
| `UPLOAD_FAILED` | Could not save document to inbox |
| `UPLOAD_TOO_LARGE` | File exceeds `max_upload_size_mb` limit |
| `TAG_EXISTS` | Tag already assigned |
| `TAG_NOT_FOUND` | Tag not assigned to document |
| `DIRECTORY_NOT_FOUND` | Watch path does not exist |
| `PERMISSION_DENIED` | Path outside `allowed_parent_paths` |
| `PATH_NOT_ALLOWED` | Path violates security boundary |

**Implementation note:** Use the MCP SDK's `isError` flag on tool results. Do NOT use HTTP-style status codes (400, 503) — those are not part of the MCP protocol. Error codes above are embedded in the message text for programmatic debugging by clients.

---

## Security

### Path Boundaries

All tools that accept file paths (`upload_document`, `watch_directory`) validate against configured boundaries:

```yaml
mcp:
  security:
    allowed_parent_paths:
      - /home/user/documents
      - /mnt/nas/shared
    max_upload_size_mb: 5
```

- Paths outside `allowed_parent_paths` are rejected with `PATH_NOT_ALLOWED`
- Symlinks are resolved before validation to prevent escapes
- Default `allowed_parent_paths`: the configured watch directories only

### Input Validation

- All string parameters are sanitized (no path traversal via `../`)
- Document IDs are validated as positive integers
- Tag names are normalized (lowercase, trimmed, max 100 chars)
- Query strings are length-limited (max 1000 chars)

### Transport Security

- **stdio:** No additional security needed (local process communication)
- **HTTP/SSE:** See Authentication section below

---

## Authentication

### stdio Transport

No authentication required — communication is local to the machine via standard I/O.

### HTTP/SSE Transport

**Default configuration:** Bind to `localhost` (127.0.0.1) only. This means only local connections are accepted.

**API key authentication:**
- API key via `Authorization: Bearer <token>` header
- Or `X-API-Key` header

**Rate limiting:**
- Configurable per-minute request limit (default: 60)
- Applies per API key / source IP

**Network exposure (advanced):**
- Exposing the HTTP transport beyond localhost requires a reverse proxy (nginx, Caddy) with TLS
- The `require_tls_for_network` flag warns if HTTP transport is bound to a non-localhost address without TLS
- Multi-key authentication is deferred to M10 (multi-user milestone)

**Configuration:**

```yaml
mcp:
  enabled: true
  transport: both  # stdio, http, or both
  http:
    port: 8001
    host: 127.0.0.1  # localhost only by default
    api_key: ${LIBRARIAN_MCP_KEY}
    rate_limit_requests_per_minute: 60
    require_tls_for_network: true  # warn if binding to 0.0.0.0 without TLS

  security:
    allowed_parent_paths:
      - /home/user/documents
    max_upload_size_mb: 5
```

**Warning:** If `host` is set to `0.0.0.0` and `require_tls_for_network` is `true`, Librarian logs a startup warning recommending a TLS-terminating reverse proxy. This is a warning, not a hard block — the user explicitly chooses to expose the service.

---

## Usage Examples

### Claude Desktop Configuration

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "librarian": {
      "command": "librarian",
      "args": ["mcp", "serve"]
    }
  }
}
```

### OpenClaw Configuration

Add MCP server via OpenClaw config:

```yaml
mcp:
  servers:
    librarian:
      transport: http
      url: http://localhost:8001
      api_key: ${LIBRARIAN_MCP_KEY}
```

### Example Tool Calls

**Search:**
```
User: "Find my insurance policies"

Claude calls: search_documents({"query": "insurance policy", "mode": "hybrid", "limit": 5})
```

**Get specific pages:**
```
User: "Show me pages 2-4 of that document"

Claude calls: get_document_text({"document_id": 123, "page_start": 2, "page_end": 4})
```

**Upload (file path — preferred):**
```
User: "Add this invoice to my library"

Claude calls: upload_document({"filename": "invoice.pdf", "file_path": "/home/user/downloads/invoice.pdf"})
```

**Summarize:**
```
User: "What do I have about taxes?"

Claude calls: search_documents({"query": "tax", "limit": 20})
Then synthesizes answer with citations
```

---

## Implementation Notes

1. **MCP tools are thin wrappers** — they call the service layer (`src/librarian/services/`)
2. **No duplicate logic** — all business logic lives in the service layer, shared with REST API
3. **Service layer prerequisite** — M6.5 must extract services before M7 implementation
4. **Graceful degradation** — MCP server can be disabled without affecting REST API
5. **Configurable transport** — can run stdio-only, HTTP-only, or both

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-17 | Initial specification |
| 1.1 | 2026-02-17 | Add `get_document_text` tool; fix `upload_document` (file_path primary, size limits); simplify resources (remove `library://documents`, `library://document/{id}`); fix error handling to MCP protocol format; add Security section; harden authentication (localhost default, rate limiting, TLS warnings) |
