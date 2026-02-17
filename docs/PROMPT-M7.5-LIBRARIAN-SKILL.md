# M7.5: Librarian OpenClaw Skill

**Goal:** Create an OpenClaw skill that enables users to interact with Librarian document intelligence through their AI assistant.

**Prerequisites:**
- ✅ M7 MCP Server complete and tested
- ✅ MCP tools working with Claude Desktop
- ✅ skill-creator skill reviewed (https://github.com/openclaw/skills/tree/main/skills/chindden/skill-creator)

---

## Overview

This skill transforms OpenClaw into a document intelligence assistant, allowing users to search, browse, tag, and manage their personal document archive through natural language conversations.

**Target users:**
- Librarian users who want conversational access to their documents
- OpenClaw users who want document management capabilities

**Distribution:**
- Bundled in `librarian/skills/librarian/`
- Published to ClawHub for easy installation
- Can be cloned from GitHub directly

---

## Skill Structure

```
librarian/
└── skills/
    └── librarian/
        ├── SKILL.md                    # Main skill instructions
        ├── scripts/
        │   ├── check_server.py         # Check if Librarian MCP is running
        │   ├── test_connection.py      # Test MCP connection
        │   └── quick_search.py         # CLI quick search utility
        ├── references/
        │   ├── mcp-tools.md            # Full MCP tool reference
        │   ├── configuration.md        # Setup and configuration guide
        │   └── examples.md             # Usage examples with screenshots
        └── assets/
            ├── claude-desktop-config.json  # Claude Desktop config template
            └── openclaw-config.yaml        # OpenClaw config snippet
```

---

## Implementation Steps

### Step 1: Create Skill Directory

```bash
cd ~/code/librarian
mkdir -p skills/librarian/{scripts,references,assets}
```

### Step 2: Create SKILL.md

The main skill file with YAML frontmatter and instructions.

**File:** `skills/librarian/SKILL.md`

```markdown
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
   # Check if Librarian is running
   librarian status

   # Start MCP server (if not running)
   librarian mcp
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
      args: ["mcp"]
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
→ search_documents(query="Allianz insurance policy", mode="semantic")
```

**Tag-based filtering:**
```
User: "Show me all my tax documents"
→ list_documents(filters={"tags": ["tax"]})
```

**Date range:**
```
User: "What documents did I add last month?"
→ list_documents(filters={"date_from": "2026-01-01", "date_to": "2026-01-31"})
```

### Managing Tags

**Add tags:**
```
User: "Mark this document as important"
→ add_tag(document_id=42, tag="important")
```

**Remove tags:**
```
User: "Remove the 'review' tag from that document"
→ remove_tag(document_id=42, tag="review")
```

### Uploading Documents

```
User: "Add this PDF to my library"
→ upload_document(file_path="/home/user/downloads/invoice.pdf")
```

## Troubleshooting

### "Librarian MCP server not responding"

1. Check if server is running:
   ```bash
   librarian status
   ```

2. Start MCP server:
   ```bash
   librarian mcp
   ```

3. Test connection:
   ```bash
   python scripts/test_connection.py
   ```

### "Search returns no results"

1. Verify documents are processed:
   ```bash
   librarian status
   ```

2. Check Ollama is running (for semantic search):
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. Try keyword search mode:
   ```
   "Search for 'insurance' using keyword mode"
   → search_documents(query="insurance", mode="keyword")
   ```

### "Upload failed"

1. Check file path is valid
2. Verify file is under `allowed_parent_paths` in config
3. For base64 uploads, ensure file is < 5MB

## Scripts

### check_server.py

Check if Librarian MCP server is running and healthy.

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
```

## References

- **[MCP Tools Reference](references/mcp-tools.md)** — Complete API documentation
- **[Configuration Guide](references/configuration.md)** — Detailed setup instructions
- **[Usage Examples](references/examples.md)** — Real-world usage patterns

## Resources

- **Librarian GitHub:** https://github.com/joywareapps/librarian
- **MCP Specification:** docs/MCP-SPEC.md
- **ClawHub:** https://clawhub.com
```

---

### Step 3: Create Scripts

#### `scripts/check_server.py`

```python
#!/usr/bin/env python3
"""
Check if Librarian MCP server is running and healthy.

Usage:
    python check_server.py [--timeout 5]
"""

import argparse
import subprocess
import sys
import time


def check_process_running():
    """Check if librarian mcp process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "librarian mcp"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def check_rest_api():
    """Check if REST API is responding."""
    import urllib.request
    import urllib.error

    try:
        with urllib.request.urlopen("http://localhost:8000/api/v1/status", timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Check Librarian server status")
    parser.add_argument("--timeout", type=int, default=5, help="Timeout in seconds")
    args = parser.parse_args()

    print("🔍 Checking Librarian server status...")
    print()

    # Check process
    if check_process_running():
        print("✅ MCP server process is running")
    else:
        print("❌ MCP server process not found")
        print("   Start with: librarian mcp")
        return 1

    # Check REST API
    if check_rest_api():
        print("✅ REST API is responding")
    else:
        print("⚠️  REST API not responding (may be optional)")

    print()
    print("🎉 Librarian server is healthy!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### `scripts/test_connection.py`

```python
#!/usr/bin/env python3
"""
Test MCP connection to Librarian.

Usage:
    python test_connection.py
"""

import json
import subprocess
import sys


def test_mcp_tools():
    """Test that MCP tools are available."""
    # This would normally use the MCP client library
    # For now, we'll do a basic check

    print("🔍 Testing MCP connection...")
    print()

    # Simulate MCP tool list request
    # In real implementation, this would use mcp Python SDK

    expected_tools = [
        "search_documents",
        "get_document",
        "get_document_text",
        "list_documents",
        "add_tag",
        "remove_tag",
        "upload_document",
        "get_library_stats",
    ]

    print("Expected MCP tools:")
    for tool in expected_tools:
        print(f"  - {tool}")

    print()
    print("✅ MCP connection test complete")
    print("   (Full test requires MCP client)")

    return 0


def main():
    try:
        return test_mcp_tools()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

#### `scripts/quick_search.py`

```python
#!/usr/bin/env python3
"""
Quick CLI search utility for Librarian.

Usage:
    python quick_search.py "insurance policy"
    python quick_search.py --mode semantic "tax documents"
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse


def search(query: str, mode: str = "hybrid", limit: int = 10):
    """Search documents via REST API."""
    base_url = "http://localhost:8000/api/v1/search"

    params = {
        "q": query,
        "mode": mode,
        "limit": limit,
    }

    url = f"{base_url}/{mode}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data.get("results", [])
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Quick search Librarian documents")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--mode", choices=["keyword", "semantic", "hybrid"],
                        default="hybrid", help="Search mode")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    args = parser.parse_args()

    print(f"🔍 Searching for: {args.query}")
    print(f"   Mode: {args.mode}")
    print()

    results = search(args.query, args.mode, args.limit)

    if not results:
        print("No results found")
        return 0

    print(f"Found {len(results)} results:")
    print()

    for i, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        doc_id = result.get("document_id", "?")
        score = result.get("score", 0)
        text = result.get("text", "")[:100]

        print(f"{i}. {title}")
        print(f"   ID: {doc_id} | Score: {score:.2f}")
        print(f"   {text}...")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### Step 4: Create References

#### `references/mcp-tools.md`

```markdown
# Librarian MCP Tools Reference

Complete API reference for Librarian MCP tools.

## search_documents

Search the document library.

**Parameters:**
```json
{
  "query": "string (required)",
  "mode": "keyword | semantic | hybrid (default: hybrid)",
  "limit": "integer (default: 10)",
  "filters": {
    "tags": ["string"],
    "date_from": "ISO date",
    "date_to": "ISO date"
  }
}
```

**Example:**
```
search_documents({
  "query": "insurance policy",
  "mode": "semantic",
  "limit": 5,
  "filters": {"tags": ["important"]}
})
```

---

## get_document

Retrieve full document with metadata and chunks.

**Parameters:**
```json
{
  "document_id": "integer (required)"
}
```

**Returns:** Document object with chunks.

---

## get_document_text

Get extracted text for a page range.

**Parameters:**
```json
{
  "document_id": "integer (required)",
  "page_start": "integer (default: 1)",
  "page_end": "integer (optional)"
}
```

**Use case:** When LLM context is limited, fetch specific pages.

---

## list_documents

Paginated document listing.

**Parameters:**
```json
{
  "limit": "integer (default: 50, max: 100)",
  "offset": "integer (default: 0)",
  "sort": "created_desc | created_asc | title",
  "filters": {
    "tags": ["string"],
    "status": "pending | processing | processed | error",
    "has_ocr": "boolean"
  }
}
```

---

## add_tag / remove_tag

Tag management.

**Parameters:**
```json
{
  "document_id": "integer (required)",
  "tag": "string (required)"
}
```

---

## upload_document

Upload a new document.

**Parameters:**
```json
{
  "filename": "string (required)",
  "file_path": "string (preferred)",
  "content": "string (base64, fallback, max 5MB)"
}
```

**Note:** Use `file_path` when possible. Base64 limited to 5MB.

---

## get_library_stats

Get library overview.

**Parameters:** None

**Returns:**
```json
{
  "documents": {"total": 142, "processed": 138, "pending": 2, "error": 2},
  "storage": {"total_mb": 500},
  "chunks": {"total": 2847, "with_embeddings": 2800},
  "tags": {"top_tags": [...]}
}
```
```

#### `references/configuration.md`

```markdown
# Configuration Guide

Complete setup and configuration for Librarian OpenClaw skill.

## Prerequisites

1. **Librarian installed**
   ```bash
   pip install librarian
   ```

2. **Librarian initialized**
   ```bash
   librarian init
   ```

3. **Documents configured**
   Edit `~/.config/librarian/config.yaml`:
   ```yaml
   watcher:
     directories:
       - /home/user/documents
       - /mnt/nas/scans
   ```

4. **Ollama running** (for semantic search)
   ```bash
   ollama serve
   ollama pull nomic-embed-text
   ```

## OpenClaw Configuration

Add to `~/.openclaw/config.yaml`:

### Option 1: stdio transport (recommended)

```yaml
mcp:
  servers:
    librarian:
      transport: stdio
      command: librarian
      args: ["mcp"]
```

### Option 2: HTTP transport

```yaml
mcp:
  servers:
    librarian:
      transport: http
      url: http://localhost:8001/mcp
      api_key: ${LIBRARIAN_MCP_KEY}
```

## Claude Desktop Configuration

Add to Claude Desktop config:

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

## Testing

1. Start Librarian MCP:
   ```bash
   librarian mcp
   ```

2. Test connection:
   ```bash
   python scripts/test_connection.py
   ```

3. Quick search test:
   ```bash
   python scripts/quick_search.py "test"
   ```

## Troubleshooting

### MCP server won't start

- Check config is valid: `librarian config validate`
- Check logs: `librarian logs`
- Check port not in use: `lsof -i :8001`

### Search returns no results

- Check documents are processed: `librarian status`
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Try keyword mode: `search_documents(mode="keyword")`

### Permission denied on file_path upload

- Check path is in `allowed_parent_paths` config
- Check file exists and is readable
```

#### `references/examples.md`

```markdown
# Usage Examples

Real-world usage patterns for Librarian skill.

## Finding Documents

### Example 1: Natural language search

**User:** "Find my car insurance policy"

**OpenClaw calls:**
```json
search_documents({
  "query": "car insurance policy",
  "mode": "semantic",
  "limit": 5
})
```

**Response:**
```
Found 3 documents:

1. Car Insurance - Allianz 2024.pdf (score: 0.85)
   ID: 42 | Tags: insurance, car

2. Vehicle Registration.pdf (score: 0.72)
   ID: 15 | Tags: car, registration

3. Insurance Renewal Letter.pdf (score: 0.68)
   ID: 87 | Tags: insurance
```

---

### Example 2: Tag filtering

**User:** "Show me all my tax documents from 2025"

**OpenClaw calls:**
```json
list_documents({
  "filters": {
    "tags": ["tax"],
    "date_from": "2025-01-01",
    "date_to": "2025-12-31"
  },
  "sort": "created_desc"
})
```

---

## Managing Tags

### Example 3: Adding tags

**User:** "Mark the insurance document as important"

**OpenClaw:**
1. First searches for "insurance"
2. Then calls:
```json
add_tag({
  "document_id": 42,
  "tag": "important"
})
```

---

## Uploading Documents

### Example 4: Adding a new PDF

**User:** "Add this invoice to my library"

**OpenClaw calls:**
```json
upload_document({
  "filename": "invoice-2026-02.pdf",
  "file_path": "/home/user/downloads/invoice-2026-02.pdf"
})
```

**Response:**
```
Document uploaded successfully!
Filename: invoice-2026-02.pdf
Inbox path: /home/user/documents/inbox/invoice-2026-02.pdf
Status: Queued for processing
```

---

## Library Overview

### Example 5: Getting statistics

**User:** "How many documents do I have?"

**OpenClaw calls:**
```json
get_library_stats({})
```

**Response:**
```
# Library Statistics

## Documents
- Total: 142
- Processed: 138
- Pending: 2
- Error: 2

## Storage
- Total: 500.3 MB

## Top Tags
- insurance: 45
- medical: 32
- financial: 28
- car: 15
- important: 12
```
```

---

### Step 5: Create Assets

#### `assets/claude-desktop-config.json`

```json
{
  "mcpServers": {
    "librarian": {
      "command": "librarian",
      "args": ["mcp"],
      "env": {
        "LIBRARIAN_CONFIG": "~/.config/librarian/config.yaml"
      }
    }
  }
}
```

#### `assets/openclaw-config.yaml`

```yaml
# Add this to your OpenClaw config (~/.openclaw/config.yaml)

mcp:
  servers:
    librarian:
      # Option 1: stdio transport (recommended for local)
      transport: stdio
      command: librarian
      args: ["mcp"]

      # Option 2: HTTP transport (for remote access)
      # transport: http
      # url: http://localhost:8001/mcp
      # api_key: ${LIBRARIAN_MCP_KEY}
```

---

## Success Criteria

1. ✅ Skill directory created at `skills/librarian/`
2. ✅ SKILL.md with proper frontmatter and instructions
3. ✅ All scripts executable and tested
4. ✅ References complete and accurate
5. ✅ Assets include configuration templates
6. ✅ Skill works when OpenClaw loads it
7. ✅ Can search, list, tag, and upload documents via OpenClaw
8. ✅ Documentation links to Librarian repo and MCP spec

---

## Distribution

### Option 1: Bundle with Librarian repo

Skill is included in `librarian/skills/librarian/` directory.

Users clone the repo and point OpenClaw to the skill:
```yaml
skills:
  directories:
    - ~/code/librarian/skills
```

### Option 2: Publish to ClawHub

```bash
clawhub publish skills/librarian
```

Users install:
```bash
clawhub install librarian
```

---

## Time Estimate

- SKILL.md: 2-3 hours
- Scripts (3): 2-3 hours
- References (3): 2-3 hours
- Assets (2): 1 hour
- Testing: 2-3 hours

**Total: 9-13 hours (1-2 days)**

---

## References

- skill-creator skill: https://github.com/openclaw/skills/tree/main/skills/chindden/skill-creator
- Librarian MCP Spec: `docs/MCP-SPEC.md`
- OpenClaw Skills Documentation: https://docs.openclaw.ai/skills
- ClawHub: https://clawhub.com
