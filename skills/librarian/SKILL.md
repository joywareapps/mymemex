---
name: librarian
description: Document intelligence for your personal archive. Search, browse, tag, and manage PDFs and scanned documents through natural language. Use when the user wants to find documents, search their files, manage tags, upload new documents, or get library statistics. Works with Librarian MCP server (must be running).
---

# Librarian Document Intelligence

Connect OpenClaw to your personal document archive. Search across PDFs, scanned documents, and images using natural language queries.

## Quick Start

### Prerequisites

1. **Librarian must be installed and running**
   ```bash
   # Start MCP server
   librarian mcp serve
   ```

2. **MCP connection configured in OpenClaw**
   See [Configuration](#configuration) section.

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

This skill uses these Librarian MCP tools:

| Tool | Description |
|------|-------------|
| `search_documents` | Keyword, semantic, or hybrid search |
| `get_document` | Retrieve full document with content |
| `get_document_text` | Get text for specific page range |
| `list_documents` | Paginated document listing |
| `add_tag` / `remove_tag` | Tag management |
| `upload_document` | Add new documents |
| `get_library_stats` | Library overview |

See [references/mcp-tools.md](references/mcp-tools.md) for complete API reference.

## Configuration

### OpenClaw Configuration

Add Librarian MCP server to your OpenClaw config:

```yaml
# ~/.openclaw/config.yaml
mcp:
  servers:
    librarian:
      transport: stdio
      command: librarian
      args: ["mcp", "serve"]
```

Or for HTTP transport:
```yaml
mcp:
  servers:
    librarian:
      transport: http
      url: http://localhost:8001/mcp
```

### Claude Desktop Configuration

See [assets/claude-desktop-config.json](assets/claude-desktop-config.json) for template.

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

## Troubleshooting

### "Librarian MCP server not responding"

1. Start MCP server:
   ```bash
   librarian mcp serve
   ```

2. Test connection:
   ```bash
   python scripts/test_connection.py
   ```

### "Search returns no results"

1. Check documents are processed:
   ```bash
   python scripts/check_server.py
   ```

2. Check Ollama is running (for semantic search):
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. Try keyword search mode:
   ```
   "Search for 'insurance' using keyword mode"
   -> search_documents(query="insurance", mode="keyword")
   ```

### "Upload failed"

1. Check file path is valid and file exists
2. Verify file is under `allowed_parent_paths` in config
3. For base64 uploads, ensure file is < 5MB

## Scripts

### check_server.py

Check if Librarian REST API is running and healthy.

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

- **[MCP Tools Reference](references/mcp-tools.md)** -- Complete API documentation
- **[Configuration Guide](references/configuration.md)** -- Detailed setup instructions
- **[Usage Examples](references/examples.md)** -- Real-world usage patterns

## Resources

- **Librarian GitHub:** https://github.com/joywareapps/librarian
- **MCP Specification:** docs/MCP-SPEC.md
- **ClawHub:** https://clawhub.com
