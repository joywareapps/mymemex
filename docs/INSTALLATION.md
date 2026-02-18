# Installation Guide

## Quick Start (pip)

```bash
# Install
pip install -e ".[dev,ocr,ai,mcp]"

# Initialize
librarian init

# Edit config
nano ~/.local/share/librarian/config.yaml

# Start
librarian serve
```

Open http://localhost:8000/ui/

## Docker (Recommended for Production)

### Standalone (Cloud LLM or no AI)

```bash
# Create config
mkdir -p ~/librarian/config
curl -o ~/librarian/config/config.yaml \
  https://raw.githubusercontent.com/joywareapps/librarian/main/config/config.example.yaml

# Edit config
nano ~/librarian/config/config.yaml

# Run
docker compose up -d
```

### Full Stack (with Ollama)

```bash
docker compose -f docker-compose.full.yml up -d

# Pull a model into Ollama
docker exec librarian-ollama ollama pull llama3.2
```

Set `llm.provider: ollama` and `llm.api_base: http://ollama:11434` in your config.

## LLM Configuration

Librarian uses an LLM for document classification and structured extraction. Without an LLM, documents are still ingested and searchable, but auto-tagging and metadata extraction are disabled.

### Option 1: Ollama (Local, Free)

```yaml
llm:
  provider: ollama
  model: llama3.2
  api_base: http://localhost:11434
```

Install Ollama: https://ollama.com/download

```bash
ollama pull llama3.2
```

### Option 2: OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
```

Set your API key via environment variable or config:

```bash
export OPENAI_API_KEY=sk-...
# Or in .env file
# Or in config.yaml: llm.api_key: sk-...
```

### Option 3: Anthropic

```yaml
llm:
  provider: anthropic
  model: claude-haiku-4-5-20251001
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## MCP Server (Claude Desktop)

Add to your Claude Desktop config (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "librarian": {
      "command": "librarian",
      "args": ["mcp", "serve", "--config", "/path/to/config.yaml"]
    }
  }
}
```

## Backup & Restore

```bash
# Create backup
librarian backup create

# List backups
librarian backup list

# Restore
librarian backup restore ./backups/librarian_backup_20260218_120000
```

Docker:

```bash
docker exec librarian librarian backup create
docker exec librarian librarian backup list
```
