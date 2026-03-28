# MyMemex

> Your AI Document Memory — For 80 years it was science fiction. Now, it's yours.

**[mymemex.app](https://mymemex.app/ui/)** • **[GitHub](https://github.com/joywareapps/mymemex)** • **[Documentation](docs/)**

---

## What is MyMemex?

MyMemex transforms your personal document archive (PDFs, scans, images) into an AI-powered memory system. Search with natural language, auto-extract structured data, and chat with your documents through MCP.

**Privacy-first:** Run fully air-gapped with local LLMs via [Ollama](https://ollama.ai). Your documents never leave your machine.

Named after [Vannevar Bush's 1945 vision](https://en.wikipedia.org/wiki/Memex) of a personal knowledge system — finally made real with AI.

## Core Features

- **Intelligent Ingestion** — Watch directories, auto-detect files, deduplicate by hash
- **100% Private** — Local OCR (Tesseract) + local LLMs (Ollama). No cloud required.
- **Semantic Search** — Ask questions in natural language, get instant answers with citations
- **Auto-Extraction** — AI extracts amounts, dates, entities, and categories automatically
- **Tag-Based Filing** — Automatic routing rules move files to tag-matched subdirectories
- **Multi-User Auth** — JWT-based login with per-user access control
- **Admin Panel** — Watch folders, routing rules, queue management, logs, backup
- **MCP Integration** — Works with Claude Desktop, OpenClaw, and other AI assistants via stdio or HTTP transport

## Quick Start

### Docker (Recommended)

```bash
# Pull and run
docker run -d -p 8000:8000 ghcr.io/joywareapps/mymemex:latest

# Or with docker-compose
curl -O https://raw.githubusercontent.com/joywareapps/mymemex/main/docker-compose.yml
docker-compose up -d
```

Visit `http://localhost:8000/ui/` to access the web UI.

### From Source

```bash
# Clone
git clone https://github.com/joywareapps/mymemex.git
cd mymemex

# Install
pip install -e ".[all]"

# Configure
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your document paths

# Run
mymemex serve
```

### Personal Instance (Private Deploy)

Use `scripts/deploy-private.sh` with a `.env` file:

```bash
LIBRARY_PATH=/path/to/your/library   # must contain inbox/ and archive/
PRIVATE_HTTP_PORT=8002
MYMEMEX_LLM__PROVIDER=ollama
MYMEMEX_LLM__API_BASE=http://your-ollama-host:11434
MYMEMEX_LLM__MODEL=gemma3:12b
```

```bash
bash scripts/deploy-private.sh
# Access at http://localhost:8002/ui/
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for all deployment options.

### MCP for Claude Desktop

**stdio transport (local install):**
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

**HTTP transport (Docker instance):**

Enable in Settings → MCP → Transport → `http`, then:
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

Now Claude can search your documents, extract data, and answer questions about your archive.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Watcher   │────▶│  Ingestion  │────▶│ OCR / Embed │
│ (filesystem)│     │   Pipeline  │     │  (Tesseract)│
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                    ┌─────────────────────────────────────┐
                    │           STORAGE LAYER             │
                    │  SQLite (metadata) + ChromaDB       │
                    └─────────────────────────────────────┘
                                               │
                      ┌────────────────────────┼────────────────────────┐
                      ▼                        ▼                        ▼
              ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
              │  Web UI     │          │  REST API   │          │  MCP Server │
              │  (search)   │          │  (CRUD)     │          │  (Claude)   │
              └─────────────┘          └─────────────┘          └─────────────┘
```

## Project Structure

```
mymemex/
├── src/mymemex/
│   ├── api/            # REST API endpoints
│   ├── core/           # Queue, events, watcher, scheduler
│   ├── processing/     # Ingestion pipeline
│   ├── intelligence/   # Embeddings + OCR
│   ├── services/       # Business logic
│   ├── storage/        # Database + vector store
│   ├── web/            # Web UI routes + templates
│   ├── mcp/            # MCP server (stdio + HTTP)
│   └── middleware/     # Auth, demo mode, MCP auth
├── skills/             # OpenClaw skill definitions
├── website/            # Astro marketing website
├── workers/            # Cloudflare Workers
├── config/             # Configuration
├── tests/              # Test suite (202 tests)
└── docs/               # Documentation
```

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.10+ | 3.12+ |
| RAM | 4GB | 8GB+ |
| Storage | 10GB | 50GB+ (depends on docs) |
| Ollama | Optional | For local AI |

### With Ollama (Local AI)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull nomic-embed-text  # Embeddings (274MB)
ollama pull gemma3:12b        # Chat/reasoning (larger)
```

Configure via `.env` or `config.yaml`:
```bash
MYMEMEX_LLM__PROVIDER=ollama
MYMEMEX_LLM__API_BASE=http://localhost:11434
MYMEMEX_LLM__MODEL=gemma3:12b
MYMEMEX_AI__SEMANTIC_SEARCH_ENABLED=true
MYMEMEX_AI__EMBEDDING_MODEL=nomic-embed-text
```

### Without Ollama (Cloud AI)

```bash
MYMEMEX_LLM__PROVIDER=openai   # or anthropic
MYMEMEX_LLM__API_KEY=sk-...
MYMEMEX_LLM__MODEL=gpt-4o
```

## Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — All deployment options (local, private, demo, production)
- **[docs/MILESTONES.md](docs/MILESTONES.md)** — Project roadmap and history
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Technical deep dive
- **[docs/SPECIFICATION.md](docs/SPECIFICATION.md)** — Full feature specification
- **[skills/mymemex/SKILL.md](skills/mymemex/SKILL.md)** — MCP tools reference for OpenClaw

## Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1–M6 | ✅ Complete | Core features (ingest, OCR, search, classify, extract) |
| M7 | ✅ Complete | MCP Server for Claude (stdio) |
| M8 | ✅ Complete | Web UI |
| M9 | ✅ Complete | Structured extraction + amounts |
| M10 | ✅ Complete | Cloud LLM support (OpenAI, Anthropic) |
| M11 | ✅ Complete | Admin panel |
| M12 | ✅ Complete | Multi-user auth + login |
| M12.5–M12.7 | ✅ Complete | AI pause/resume, tag-based routing, MCP HTTP, SQLite retry |
| M13 | 🔜 Planned | Chat interface, document Q&A |

**202 tests passing** • **[Live demo](https://mymemex.app/ui/) — read-only, no sign-up**

## License

**AGPL v3 + Commercial Dual License**

- **Free** for personal/open-source use ([AGPL v3](LICENSE))
- **Commercial license** available for businesses ([contact](mailto:contact@mymemex.io))

## Support the Project

If you find MyMemex useful, consider:

- **Starring the repo** on GitHub
- **Sponsoring development** (GitHub Sponsors)

See [SUPPORTERS.md](SUPPORTERS.md) for supporter benefits.

---

*"Thus science may implement the ways in which man produces, stores, and consults the record of the race."*
— **Vannevar Bush**, 1945

---

**[Live Demo](https://mymemex.app/ui/)** • **[View on GitHub](https://github.com/joywareapps/mymemex)** • **[Report Issue](https://github.com/joywareapps/mymemex/issues)**
