# Librarian - Project Status

**Last Updated:** 2026-02-17
**Phase:** M1-M8 Complete | Production Ready

## Current State

- M1-M8 complete (102 tests passing)
- MCP Server with 8 tools, 2 resources, 2 prompts
- Web UI for document browsing, search, tags, upload
- Semantic search with Ollama embeddings + ChromaDB
- OCR via Tesseract for scanned PDFs
- Startup recovery for crashed tasks and stuck documents

## Completed Milestones

| Milestone | Description |
|-----------|-------------|
| **M1** | Project skeleton, config system, CLI |
| **M2** | SQLite database, SQLAlchemy models |
| **M3** | File watcher, deduplication (SHA-256), task queue |
| **M4** | Text extraction (PyMuPDF), chunking, FTS5 search |
| **M5** | OCR integration (Tesseract) for scanned PDFs |
| **M6** | Vector embeddings + semantic search (Ollama + ChromaDB) |
| **M6.5** | Service layer extraction |
| **M7** | MCP Server (8 tools, 2 resources, 2 prompts) |
| **M7.5** | OpenClaw skill for Librarian |
| **M8** | Web UI (document browser, search, tags, upload) |

## Next Steps

### M9: Auto-Tagging
- [ ] LLM-based document classification on ingest
- [ ] Tag suggestions based on content
- [ ] Confidence thresholds

### M9.5: Structured Extraction & Aggregation
- [ ] Extract structured data (amounts, dates, entities) from documents via LLM
- [ ] `document_fields` table with typed values for SQL aggregation
- [ ] MCP tools: `aggregate_amounts`, `get_extracted_fields`, `list_document_types`
- [ ] Enable queries like "How much tax did I pay 2015-2025?"

### M10: Multi-User Support
- [ ] Named profiles
- [ ] Document ownership tracking
- [ ] Per-user filtering

## Blockers

None currently.

## Notes

- Target hardware: Synology NAS (16GB RAM) or equivalent
- Privacy-first: local processing by default
- 102 tests passing (unit + integration)
- See [TODO.md](TODO.md) for known issues
- See [docs/MILESTONES.md](docs/MILESTONES.md) for full roadmap
