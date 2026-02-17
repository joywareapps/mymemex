# Librarian MCP Tools Reference

Complete API reference for Librarian MCP tools.

## search_documents

Search the document library using keyword, semantic, or hybrid search.

**Parameters:**
```json
{
  "query": "string (required)",
  "mode": "keyword | semantic | hybrid (default: hybrid)",
  "limit": "integer (default: 10)"
}
```

**Modes:**
- `keyword` -- Full-text search using SQLite FTS5. Always available, no LLM needed.
- `semantic` -- Vector similarity search using embeddings. Requires Ollama with nomic-embed-text.
- `hybrid` -- Combines keyword + semantic using Reciprocal Rank Fusion. Falls back to keyword-only when semantic is unavailable.

**Example:**
```
search_documents(query="insurance policy", mode="semantic", limit=5)
```

---

## get_document

Retrieve full document metadata and content chunks.

**Parameters:**
```json
{
  "document_id": "integer (required)"
}
```

**Returns:** Document metadata (title, filename, path, size, page count, status, tags) and up to 10 content chunks.

**Error:** `[DOCUMENT_NOT_FOUND]` if document ID is invalid.

---

## get_document_text

Get extracted text for a specific page range. Useful for LLM workflows where loading the full document would exceed context limits.

**Parameters:**
```json
{
  "document_id": "integer (required)",
  "page_start": "integer (default: 1)",
  "page_end": "integer (optional, default: last page)"
}
```

**Example:**
```
get_document_text(document_id=42, page_start=2, page_end=4)
```

---

## list_documents

Paginated document listing with optional filters.

**Parameters:**
```json
{
  "limit": "integer (default: 50, max: 100)",
  "offset": "integer (default: 0)",
  "status": "pending | processing | processed | error (optional)",
  "category": "string (optional)",
  "tag": "string (optional)",
  "sort": "created_desc | created_asc | title (default: created_desc)"
}
```

---

## add_tag

Add a tag to a document. Creates the tag if it doesn't exist.

**Parameters:**
```json
{
  "document_id": "integer (required)",
  "tag": "string (required)"
}
```

**Error:** `[DOCUMENT_NOT_FOUND]` if document ID is invalid.

---

## remove_tag

Remove a tag from a document.

**Parameters:**
```json
{
  "document_id": "integer (required)",
  "tag": "string (required)"
}
```

**Error:** `[TAG_NOT_FOUND]` if tag is not assigned to the document.

---

## upload_document

Upload a new document to the library. Provide either a local file path (preferred) or base64-encoded content.

**Parameters:**
```json
{
  "filename": "string (required)",
  "file_path": "string (preferred for local files)",
  "content": "string (base64-encoded, fallback, max 5MB)"
}
```

**Notes:**
- Exactly one of `file_path` or `content` must be provided
- `file_path` is validated against `allowed_parent_paths` in config
- Document is queued for processing (not immediately available)

**Errors:**
- `[INVALID_PARAMETERS]` -- Missing or conflicting parameters
- `[UPLOAD_TOO_LARGE]` -- File exceeds size limit
- `[UPLOAD_FAILED]` -- Could not save document

---

## get_library_stats

Get overall library statistics. No parameters required.

**Returns:** Document counts (total, processed, pending, error), storage size, chunk count, and queue status.
