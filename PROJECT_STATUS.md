# Librarian - Project Status

**Last Updated:** 2026-02-18
**Phase:** M1-M10 Complete | Production Ready

## Current State

- M1-M10 complete (141 tests passing)
- Pre-built Docker images (GHCR)
- Cloud LLM support (OpenAI, Anthropic)
- MCP Server with 13 tools
- Backup CLI for database + vectors
- Web UI for document browsing, search, tags, upload

## Completed Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| **M1** | Project skeleton, config system, CLI | ✅ |
| **M2** | SQLite database, SQLAlchemy models | ✅ |
| **M3** | File watcher, deduplication (SHA-256), task queue | ✅ |
| **M4** | Text extraction (PyMuPDF), chunking, FTS5 search | ✅ |
| **M5** | OCR integration (Tesseract) for scanned PDFs | ✅ |
| **M6** | Vector embeddings + semantic search (Ollama + ChromaDB) | ✅ |
| **M6.5** | Service layer extraction | ✅ |
| **M7** | MCP Server (13 tools, 2 resources, 2 prompts) | ✅ |
| **M7.5** | OpenClaw skill for Librarian | ✅ |
| **M8** | Web UI (document browser, search, tags, upload) | ✅ |
| **M9** | Auto-Tagging via LLM | ✅ |
| **M9.5** | Structured Extraction & Aggregation | ✅ |
| **M10** | Deployment & Distribution | ✅ |

## M10 Features

- **Pre-built Docker images** — `ghcr.io/joywareapps/librarian:latest`
- **Cloud LLM support** — OpenAI, Anthropic (for users without Ollama)
- **API key configuration** — Environment variables (`.env` file)
- **Backup CLI** — `librarian backup create/list/restore`
- **docker-compose.full.yml** — Full stack with Ollama
- **Installation docs** — `docs/INSTALLATION.md`

## Upcoming Milestones

| Milestone | Description |
|-----------|-------------|
| **M11** | Admin Panel & File Management |
| **M12** | Multi-User Support |
| **M13** | Chat Interface |
| **M14** | Cloud OCR Fallback |

## Deployment Options

| Method | Command |
|--------|---------|
| Docker (standalone) | `docker pull ghcr.io/joywareapps/librarian:latest` |
| Docker Compose | `docker-compose up -d` |
| Full Stack | `docker-compose -f docker-compose.full.yml up -d` |
| pip | `pip install librarian[ocr,ai,mcp]` |

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `search_documents` | Keyword/semantic/hybrid search |
| `get_document` | Retrieve document details |
| `get_document_text` | Get text by page range |
| `list_documents` | Paginated document listing |
| `add_tag` / `remove_tag` | Tag management |
| `upload_document` | File upload |
| `get_library_stats` | Library statistics |
| `aggregate_amounts` | Sum monetary values across documents |
| `get_extracted_fields` | View extracted metadata |
| `list_document_types` | List auto-classified types |
| `reextract_documents` | Re-run extraction |
| `classify_document` | Manual classification trigger |

## Blockers

None currently.

## Notes

- 141 tests passing (unit + integration)
- Cloud LLM optional (OpenAI/Anthropic via env vars)
- Local-first: Ollama works offline
- See [TODO.md](TODO.md) for known issues
- See [docs/MILESTONES.md](docs/MILESTONES.md) for full roadmap
- See [docs/INSTALLATION.md](docs/INSTALLATION.md) for setup guide
