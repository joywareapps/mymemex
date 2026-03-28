---
name: mymemex
description: Document intelligence for your personal archive. Search, browse, tag, and manage PDFs and scanned documents through natural language. Use when the user wants to find documents, search their files, manage tags, upload new documents, or get library statistics. Works with MyMemex MCP server (must be running).
---

# MyMemex Document Intelligence

Connect to your personal document archive. Search across PDFs, scanned documents, and images using natural language queries.

## Quick Start

### Prerequisites

MyMemex must be running and MCP must be reachable. Two options:

**Option A — HTTP transport (Docker instance):**
Set `mcp.transport = http` in MyMemex Settings, then configure OpenClaw/Claude Desktop to connect via URL (see [Configuration](#configuration)).

**Option B — stdio transport (local install):**
```bash
mymemex mcp serve
```

### Basic Usage

**Search your documents:**
```
"Search my documents for insurance policies"
"Find anything about taxes from last year"
"What do I have about medical certificates?"
```

**Browse and manage:**
```
"Show me recent documents"
"List all documents tagged 'important'"
"Tag document 42 as 'receipt'"
```

**Library overview:**
```
"How many documents do I have?"
"What are my most used tags?"
"Show library statistics"
```

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `search_documents` | Keyword, semantic, or hybrid search |
| `get_document` | Retrieve full document with content chunks |
| `get_document_text` | Get text for a specific page range |
| `list_documents` | Paginated document listing with filters |
| `add_tag` / `remove_tag` | Tag management |
| `upload_document` | Add new documents (file path or base64) |
| `get_library_stats` | Library overview and queue status |
| `get_extracted_fields` | View LLM-extracted structured fields |
| `aggregate_amounts` | Aggregate monetary totals (e.g., tax, spending) |
| `reclassify_documents` | Re-classify documents with LLM |
| `reextract_documents` | Re-run structured extraction with LLM |
| `list_document_types` | List all auto-classified categories with counts |

See [references/mcp-tools.md](references/mcp-tools.md) for complete API reference.

## MCP Resources

| Resource URI | Description |
|---|---|
| `library://tags` | All tags with document counts |
| `library://stats` | Overall library statistics (JSON) |

## MCP Prompts

| Prompt | Description |
|---|---|
| `search_and_summarize(query)` | Search and summarize key findings |
| `compare_documents(document_ids)` | Compare two or more documents side by side |

## Configuration

### OpenClaw — HTTP transport (recommended for Docker)

```yaml
# ~/.openclaw/config.yaml
mcp:
  servers:
    mymemex:
      transport: http
      url: http://your-server:8002/mcp
      # api_key: ${MYMEMEX_MCP_KEY}   # if MCP auth token is enabled
```

### OpenClaw — stdio transport (local install)

```yaml
# ~/.openclaw/config.yaml
mcp:
  servers:
    mymemex:
      transport: stdio
      command: mymemex
      args: ["mcp", "serve"]
```

### Claude Desktop — stdio transport

See [assets/claude-desktop-config.json](assets/claude-desktop-config.json) for template.

For HTTP transport, Claude Desktop uses:
```json
{
  "mcpServers": {
    "mymemex": {
      "type": "http",
      "url": "http://your-server:8002/mcp"
    }
  }
}
```

## Common Workflows

### Finding Documents

**Natural language search:**
```
User: "Find my insurance policy from Allianz"
-> search_documents(query="Allianz insurance policy", mode="semantic")
```

**Tag-based filtering:**
```
User: "Show me all my tax documents"
-> list_documents(tag="tax")
```

**Page-specific retrieval:**
```
User: "Show me pages 2-4 of that document"
-> get_document_text(document_id=42, page_start=2, page_end=4)
```

### Managing Tags

**Add tags:**
```
User: "Mark this document as important"
-> add_tag(document_id=42, tag="important")
```

**Remove tags:**
```
User: "Remove the 'review' tag from that document"
-> remove_tag(document_id=42, tag="review")
```

### Uploading Documents

```
User: "Add this PDF to my library"
-> upload_document(filename="invoice.pdf", file_path="/home/user/downloads/invoice.pdf")
```

### Aggregating Amounts

```
User: "How much tax did I pay from 2015 to 2025?"
-> aggregate_amounts(field_name="total_tax", date_from="2015-01-01", date_to="2025-12-31")
```

## Troubleshooting

### "MCP server not responding" (HTTP mode)

1. Check the container is running: `docker ps | grep mymemex`
2. Verify MCP transport is set to `http` in Settings → MCP
3. Test the endpoint: `curl http://your-server:8002/mcp`

### "MCP server not responding" (stdio mode)

1. Start MCP server:
   ```bash
   mymemex mcp serve
   ```

2. Test connection:
   ```bash
   python scripts/test_connection.py
   ```

### "Search returns no results"

1. Check documents are processed: `get_library_stats`
2. Try keyword search mode (no LLM required):
   ```
   "Search for 'insurance' using keyword mode"
   -> search_documents(query="insurance", mode="keyword")
   ```
3. For semantic search — check Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```

### "Upload failed"

1. Check the file path is valid and the file exists
2. Verify file is under `allowed_parent_paths` in config
3. For base64 uploads, ensure file is < 5MB

## Scripts

### check_server.py

Check if MyMemex REST API is running and healthy.

```bash
python scripts/check_server.py
```

### test_connection.py

Test MCP connection and verify tools are available.

```bash
python scripts/test_connection.py
```

### quick_search.py

Quick CLI search utility for testing.

```bash
python scripts/quick_search.py "insurance policy"
python scripts/quick_search.py --mode keyword "tax"
```

## References

- **[MCP Tools Reference](references/mcp-tools.md)** — Complete API documentation
- **[Configuration Guide](references/configuration.md)** — Detailed setup instructions
- **[Usage Examples](references/examples.md)** — Real-world usage patterns

## Resources

- **MyMemex GitHub:** https://github.com/joywareapps/mymemex
