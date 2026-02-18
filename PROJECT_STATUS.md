# Librarian - Project Status

**Last Updated:** 2026-02-18
**Phase:** M1-M9.5 Complete | Ready for Deployment

## Current State

- M1-M9.5 complete (139 tests passing)
- MCP Server with 13 tools (search, extraction, aggregation)
- Web UI for document browsing, search, tags, upload
- Semantic search with Ollama embeddings + ChromaDB
- OCR via Tesseract for scanned PDFs
- Auto-tagging and structured extraction via LLM
- Concurrent upload handling with semaphore

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

## In Progress

### M10: Deployment & Distribution
- [ ] Pre-built Docker images (GHCR)
- [ ] Cloud LLM support (OpenAI, Anthropic)
- [ ] API key configuration via environment
- [ ] Backup CLI commands
- [ ] User documentation

## Upcoming Milestones

| Milestone | Description |
|-----------|-------------|
| **M11** | Admin Panel & File Management |
| **M12** | Multi-User Support |
| **M13** | Chat Interface |
| **M14** | Cloud OCR Fallback |

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

- Target hardware: Synology NAS or any Docker host
- Privacy-first: local processing by default
- Cloud LLM optional (OpenAI/Anthropic)
- 139 tests passing (unit + integration)
- See [TODO.md](TODO.md) for known issues
- See [docs/MILESTONES.md](docs/MILESTONES.md) for full roadmap
