# Configuration Guide

Complete setup and configuration for MyMemex OpenClaw skill.

## Prerequisites

1. **MyMemex installed**
   ```bash
   pip install mymemex
   ```

2. **MyMemex initialized**
   ```bash
   mymemex init
   ```

3. **Documents configured**
   Edit `~/.config/mymemex/config.yaml`:
   ```yaml
   watch:
     directories:
       - /home/user/documents
       - /mnt/nas/scans
   ```

4. **Ollama running** (optional, for semantic search)
   ```bash
   ollama serve
   ollama pull nomic-embed-text
   ```

## OpenClaw Configuration

Add to `~/.openclaw/config.yaml`:

```yaml
mcp:
  servers:
    mymemex:
      transport: stdio
      command: mymemex
      args: ["mcp", "serve"]
```

## Claude Desktop Configuration

Add to Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mymemex": {
      "command": "mymemex",
      "args": ["mcp", "serve"]
    }
  }
}
```

## MCP Security Configuration

Configure path boundaries and upload limits in `~/.config/mymemex/config.yaml`:

```yaml
mcp:
  security:
    allowed_parent_paths:
      - /home/user/documents
      - /mnt/nas/shared
    max_upload_size_mb: 5
```

- `allowed_parent_paths` restricts which directories the `upload_document` tool can access. Defaults to the configured watch directories if not set.
- `max_upload_size_mb` limits base64 upload size (file_path uploads are not size-limited).

## Testing

1. Start MyMemex MCP:
   ```bash
   mymemex mcp serve
   ```

2. Test tool registration:
   ```bash
   python scripts/test_connection.py
   ```

3. Quick search test (requires REST API running):
   ```bash
   mymemex serve &
   python scripts/quick_search.py "test"
   ```

## Troubleshooting

### MCP server won't start

- Check config is valid: `mymemex config --show`
- Verify database exists: `ls ~/.local/share/mymemex/mymemex.db`

### Search returns no results

- Check documents are processed: `python scripts/check_server.py`
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Try keyword mode: `search_documents(query="...", mode="keyword")`

### Permission denied on file_path upload

- Check path is under `allowed_parent_paths` in config
- Symlinks are resolved before validation -- no symlink escapes
- Check file exists and is readable
