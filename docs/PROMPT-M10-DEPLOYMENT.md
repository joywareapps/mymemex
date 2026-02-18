# M10: Deployment & Distribution Implementation Prompt

## Overview

Implement production-ready deployment for Librarian with pre-built Docker images, cloud LLM support, and backup infrastructure.

**Estimated effort:** 1-2 weeks

---

## Current State

| Component | Status |
|-----------|--------|
| Dockerfile | ✅ Exists (multi-stage, non-root user) |
| docker-compose.yml | ✅ Exists (standalone) |
| GitHub Actions | ✅ Created (needs testing) |
| Cloud LLM support | ❌ Not implemented |
| API key config | ❌ Not implemented |
| Backup CLI | ❌ Not implemented |
| User docs | ❌ Minimal |

---

## Part 1: Cloud LLM Support

### Problem

Users without local GPU/Ollama cannot use classification/extraction features.

### Solution

Support OpenAI and Anthropic via API keys configured through environment variables.

### Files to Modify

#### `src/librarian/config.py`

Add `api_key` field to `LLMConfig`:

```python
class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: Literal["ollama", "openai", "anthropic", "none"] = "none"
    model: str = ""
    api_base: str = "http://localhost:11434"
    api_key: str | None = None  # NEW: For cloud providers
```

#### `src/librarian/intelligence/llm_client.py`

Update `create_llm_client()` to read API keys:

```python
import os

def create_llm_client(config: LLMConfig) -> LLMClient:
    """Create LLM client based on config."""
    if config.provider == "ollama":
        return OllamaClient(config)
    elif config.provider == "openai":
        # Try config first, then environment
        api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required (config or OPENAI_API_KEY env)")
        return OpenAIClient(config, api_key)
    elif config.provider == "anthropic":
        api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key required (config or ANTHROPIC_API_KEY env)")
        return AnthropicClient(config, api_key)  # Needs implementation
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
```

#### `src/librarian/intelligence/llm_client.py` - Add AnthropicClient

```python
class AnthropicClient(LLMClient):
    """Anthropic LLM client."""

    def __init__(self, config: LLMConfig, api_key: str):
        self.config = config
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text via Anthropic API."""
        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": self.config.model or "claude-3-haiku-20240307",
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        response = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON via Anthropic API."""
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nReturn valid JSON only."
        text = await self.generate(json_prompt, system=system)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse Anthropic JSON", error=str(e))
            raise ValueError(f"Invalid JSON from Anthropic: {e}")
```

### Tests

Add to `tests/test_llm_client.py`:

```python
def test_openai_client_reads_env_api_key():
    """OpenAI client reads API key from environment."""
    import os
    os.environ["OPENAI_API_KEY"] = "test-key"
    config = LLMConfig(provider="openai", model="gpt-4o-mini")
    client = create_llm_client(config)
    assert isinstance(client, OpenAIClient)
    assert client.api_key == "test-key"

def test_anthropic_client_reads_env_api_key():
    """Anthropic client reads API key from environment."""
    import os
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    config = LLMConfig(provider="anthropic", model="claude-3-haiku")
    client = create_llm_client(config)
    assert isinstance(client, AnthropicClient)
```

---

## Part 2: Docker Compose Files

### `docker-compose.yml` (Standalone - External Ollama)

Update existing file:

```yaml
version: "3.8"

services:
  librarian:
    image: ghcr.io/joywareapps/librarian:latest
    container_name: librarian
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config:ro
      - librarian-data:/var/lib/librarian
      - ${DOCUMENTS_PATH:-~/Documents}:/mnt/documents:ro
    environment:
      - LIBRARIAN_CONFIG=/app/config/config.yaml
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    env_file:
      - .env  # Optional: for API keys
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M

volumes:
  librarian-data:
```

### `docker-compose.full.yml` (Full Stack - With Ollama)

Create new file:

```yaml
version: "3.8"

services:
  librarian:
    image: ghcr.io/joywareapps/librarian:latest
    container_name: librarian
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config:ro
      - librarian-data:/var/lib/librarian
      - ${DOCUMENTS_PATH:-~/Documents}:/mnt/documents:ro
    environment:
      - LIBRARIAN_CONFIG=/app/config/config.yaml
      - OLLAMA_HOST=ollama:11434
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    depends_on:
      - ollama
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  ollama:
    image: ollama/ollama:latest
    container_name: librarian-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    restart: unless-stopped
    # GPU support (uncomment if available)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

volumes:
  librarian-data:
  ollama-models:
```

### `.env.example`

Create new file:

```bash
# Librarian Environment Configuration
# Copy to .env and fill in your values

# Cloud LLM API Keys (optional - only needed if not using Ollama)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Document path (used in docker-compose)
DOCUMENTS_PATH=~/Documents
```

---

## Part 3: Backup CLI

### `src/librarian/cli/backup.py`

Create new file:

```python
"""Backup and restore commands."""

from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress

app = typer.Typer()
console = Console()


@app.command()
def create(
    destination: Path = typer.Option(
        "./backups",
        "--destination", "-d",
        help="Backup destination directory",
    ),
    include_config: bool = typer.Option(
        True,
        "--include-config/--no-config",
        help="Include config.yaml in backup",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Backup name (default: timestamp)",
    ),
) -> None:
    """Create a backup of database, vectors, and optionally config."""
    from ..config import get_config_path
    from ..storage.database import get_engine
    import shutil
    import json

    # Generate backup name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = name or f"librarian_backup_{timestamp}"
    backup_dir = destination / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Creating backup:[/] {backup_dir}")

    with Progress() as progress:
        # Backup database
        task = progress.add_task("Backing up database...", total=1)

        # Get database path from config
        config_path = get_config_path()
        # ... implementation details

        progress.update(task, advance=1)

    # Write manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "version": "1.0",
        "includes": {
            "database": True,
            "vectors": True,
            "config": include_config,
        },
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    console.print(f"[green]✓[/] Backup created: {backup_dir}")


@app.command()
def restore(
    backup_path: Path = typer.Argument(
        ...,
        help="Path to backup directory",
    ),
) -> None:
    """Restore from a backup."""
    console.print(f"[bold]Restoring from:[/] {backup_path}")

    # Verify manifest
    manifest_path = backup_path / "manifest.json"
    if not manifest_path.exists():
        console.print("[red]Error:[/] Invalid backup (no manifest.json)")
        raise typer.Exit(1)

    # ... implementation details

    console.print("[green]✓[/] Restore complete")


@app.command()
def list(
    destination: Path = typer.Option(
        "./backups",
        "--destination", "-d",
        help="Backup directory to list",
    ),
) -> None:
    """List available backups."""
    import json

    if not destination.exists():
        console.print("[yellow]No backups found[/]")
        return

    backups = sorted(destination.iterdir(), reverse=True)

    if not backups:
        console.print("[yellow]No backups found[/]")
        return

    console.print(f"[bold]Backups in {destination}:[/]")
    for backup in backups:
        manifest_path = backup / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            created = manifest.get("created_at", "unknown")
            console.print(f"  • {backup.name} ({created})")
        else:
            console.print(f"  • {backup.name} (invalid)")
```

### Register in `src/librarian/cli/__init__.py`

```python
from .backup import app as backup_app

# Add to main app
app.add_typer(backup_app, name="backup")
```

---

## Part 4: User Documentation

### `docs/INSTALLATION.md`

Create comprehensive installation guide:

```markdown
# Installation Guide

## Quick Start

### Docker (Recommended)

1. Create configuration directory:
   \`\`\`bash
   mkdir -p ~/librarian/config
   \`\`\`

2. Download example config:
   \`\`\`bash
   curl -o ~/librarian/config/config.yaml \\
     https://raw.githubusercontent.com/joywareapps/librarian/main/config/config.example.yaml
   \`\`\`

3. Edit config:
   \`\`\`bash
   nano ~/librarian/config/config.yaml
   \`\`\`

4. Run:
   \`\`\`bash
   docker run -d \\
     --name librarian \\
     -p 8000:8000 \\
     -v ~/librarian/config:/app/config:ro \\
     -v ~/librarian/data:/var/lib/librarian \\
     -v ~/Documents:/mnt/documents:ro \\
     ghcr.io/joywareapps/librarian:latest
   \`\`\`

5. Open http://localhost:8000

## LLM Configuration

### Option 1: Ollama (Local)

\`\`\`yaml
llm:
  provider: ollama
  model: llama3.2
  api_base: http://localhost:11434
\`\`\`

### Option 2: OpenAI (Cloud)

\`\`\`yaml
llm:
  provider: openai
  model: gpt-4o-mini
\`\`\`

\`\`\`bash
# .env file
OPENAI_API_KEY=sk-xxx
\`\`\`

### Option 3: Anthropic (Cloud)

\`\`\`yaml
llm:
  provider: anthropic
  model: claude-3-haiku
\`\`\`

\`\`\`bash
# .env file
ANTHROPIC_API_KEY=sk-ant-xxx
\`\`\`

## Backup

### Create backup
\`\`\`bash
docker exec librarian librarian backup create
\`\`\`

### List backups
\`\`\`bash
docker exec librarian librarian backup list
\`\`\`

### Restore
\`\`\`bash
docker exec librarian librarian backup restore /var/lib/librarian/backups/backup_name
\`\`\`
```

---

## Part 5: Update Call Sites

### Update all places that create LLM clients

Search and update:

```bash
grep -r "create_llm_client" src/
```

Update calls to not pass api_key parameter (it's now read from config/env inside the function).

---

## Testing Checklist

- [ ] `pip install -e ".[dev,ocr,ai,mcp]"` works
- [ ] `librarian serve` starts with Ollama config
- [ ] `librarian serve` starts with OpenAI config + env var
- [ ] `librarian serve` fails gracefully without API key
- [ ] `docker build -t librarian .` succeeds
- [ ] `docker run librarian` starts and responds to /health
- [ ] `librarian backup create` creates backup directory
- [ ] `librarian backup list` shows backups
- [ ] All 139+ tests pass

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/librarian/cli/backup.py` | Backup CLI commands |
| `docker-compose.full.yml` | Full stack with Ollama |
| `.env.example` | Environment variable template |
| `docs/INSTALLATION.md` | User installation guide |

## Files to Modify

| File | Change |
|------|--------|
| `src/librarian/config.py` | Add `api_key` to `LLMConfig` |
| `src/librarian/intelligence/llm_client.py` | Add `AnthropicClient`, env var support |
| `src/librarian/cli/__init__.py` | Register backup commands |
| `docker-compose.yml` | Add env_file, environment vars |
| `README.md` | Link to installation docs |

---

## Commands

```bash
cd ~/code/librarian

# Run tests
pytest -xvs

# Test Docker build
docker build -t librarian-test .

# Test with OpenAI (set env var first)
export OPENAI_API_KEY=sk-test
python -c "from librarian.intelligence.llm_client import create_llm_client; from librarian.config import LLMConfig; print(create_llm_client(LLMConfig(provider='openai', model='gpt-4o-mini')))"
```
