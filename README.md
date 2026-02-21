# MyMemex

> Your AI Document Memory — For 80 years it was science fiction. Now, it's yours.

**[mymemex.io](https://mymemex.io)** • **[GitHub](https://github.com/joywareapps/mymemex)** • **[Documentation](docs/)**

---

## What is MyMemex?

MyMemex transforms your personal document archive (PDFs, scans, images) into an AI-powered memory system. Search with natural language, auto-extract structured data, and chat with your documents.

**Privacy-first:** Run fully air-gapped with local LLMs via [Ollama](https://ollama.ai). Your documents never leave your machine.

Named after [Vannevar Bush's 1945 vision](https://en.wikipedia.org/wiki/Memex) of a personal knowledge system — finally made real with AI.

## Core Features

- 📁 **Intelligent Ingestion** — Watch directories, auto-detect files, deduplicate by hash
- 🔒 **100% Private** — Local OCR (Tesseract) + local LLMs (Ollama). No cloud required.
- 🔍 **Semantic Search** — Ask questions in natural language, get instant answers with citations
- 🤖 **Auto-Extraction** — AI extracts amounts, dates, entities, categories automatically
- 💬 **MCP Integration** — Works with Claude Desktop, OpenClaw, and other AI assistants

## Quick Start

### Docker (Recommended)

```bash
# Pull and run
docker run -d -p 8000:8000 ghcr.io/joywareapps/mymemex:latest

# Or with docker-compose
curl -O https://raw.githubusercontent.com/joywareapps/mymemex/main/docker-compose.yml
docker-compose up -d
```

Visit `http://localhost:8000` to access the web UI.

### From Source

```bash
# Clone
git clone https://github.com/joywareapps/mymemex.git
cd mymemex

# Install
pip install mymemex[all]

# Configure
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your document paths

# Run
mymemex serve
```

### MCP for Claude Desktop

Add to your `claude_desktop_config.json`:

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

Now Claude can search your documents, extract data, and answer questions about your archive.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Watcher   │────▶│  Ingestion  │────▶│  Embedding  │
│ (filesystem)│     │   Pipeline  │     │   + OCR     │
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
│   ├── watcher/        # File system monitoring
│   ├── processing/     # Ingestion pipeline
│   ├── intelligence/   # Embeddings + OCR
│   ├── services/       # Business logic
│   ├── storage/        # Database + vector store
│   └── mcp/            # MCP server for Claude
├── website/            # Astro website
├── workers/            # Cloudflare Workers
├── config/             # Configuration
├── tests/              # Test suite (140+ tests)
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

# Configure in config.yaml
llm:
  api_base: http://localhost:11434
  model: gemma3:12b
```

### Without Ollama (Cloud AI)

MyMemex also supports cloud providers:

```yaml
ai:
  provider: openai  # or anthropic
  api_key: ${OPENAI_API_KEY}
```

## Documentation

- **[Milestones](docs/MILESTONES.md)** — Project roadmap
- **[Deployment](docs/DEPLOYMENT.md)** — Production deployment guide
- **[Architecture](docs/architecture.md)** — Technical deep dive
- **[MCP Tools](docs/mcp-tools.md)** — Claude integration reference

## Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1-M6 | ✅ Complete | Core features (ingest, search, classify) |
| M7 | ✅ Complete | MCP Server for Claude |
| M8 | ✅ Complete | Web UI |
| M9 | ✅ Complete | Structured extraction |
| M10 | ✅ Complete | Cloud LLM support |
| M11 | 🔜 Planned | Admin Panel |
| M12+ | 🔜 Planned | Multi-user, Chat, Cloud OCR |

**141 tests passing** • **Zero known bugs**

## License

**AGPL v3 + Commercial Dual License**

- **Free** for personal/open-source use ([AGPL v3](LICENSE))
- **Commercial license** available for businesses ([contact](mailto:contact@mymemex.io))

## Support the Project

If you find MyMemex useful, consider:

- ⭐ **Starring the repo** on GitHub
- 💬 **Joining our [Discord](https://discord.gg/yvR8Mw9bZa)** 
- 💰 **Sponsoring development** (GitHub Sponsors / Patreon)

See [SUPPORTERS.md](SUPPORTERS.md) for supporter benefits.

---

*"Thus science may implement the ways in which man produces, stores, and consults the record of the race."*
— **Vannevar Bush**, 1945

---

**[Get Started](https://mymemex.io)** • **[View on GitHub](https://github.com/joywareapps/mymemex)** • **[Report Issue](https://github.com/joywareapps/mymemex/issues)**
