# MyMemex MCP Tools Reference

Complete API reference for MyMemex MCP tools.

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

---

## list_documents

Paginated document listing with optional filters.

**Parameters:**
```json
{
  "limit": "integer (default: 50, max: 100)",
  "offset": "integer (default: 0)",
  "status": "pending | processing | processed | failed | error (optional)",
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

---

## get_library_stats

Get overall library statistics.

**Returns:** Document counts, storage size, chunk count, and queue status.

---

## reclassify_documents

Re-classify documents using LLM to update auto-tags and document type.

**Parameters:**
```json
{
  "document_ids": "integer[] (optional)",
  "all_documents": "boolean (default: false)"
}
```

---

## reextract_documents

Re-run structured extraction on documents using LLM.

**Parameters:**
```json
{
  "document_ids": "integer[] (optional)",
  "all_documents": "boolean (default: false)"
}
```

---

## list_document_types

List all auto-classified document categories with their document counts.

**Returns:** A table of categories and counts.

---

## get_extracted_fields

View extracted structured fields (amounts, entities, dates) for a specific document.

**Parameters:**
```json
{
  "document_id": "integer (required)"
}
```

---

## aggregate_amounts

Aggregate monetary values across documents based on filters.

**Parameters:**
```json
{
  "category": "string (optional)",
  "field_name": "string (optional, e.g., 'total_tax')",
  "date_from": "string (ISO date, optional)",
  "date_to": "string (ISO date, optional)",
  "currency": "string (optional, e.g., 'EUR')",
  "min_confidence": "number (default: 0.5)"
}
```
