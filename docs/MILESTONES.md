# MyMemex: Milestones & Roadmap

**Last Updated:** 2026-03-28

---

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
| **M7.5** | OpenClaw skill for MyMemex | ✅ |
| **M8** | Web UI (document browser, search, tags, upload) | ✅ |
| **M9** | Auto-Tagging via LLM | ✅ |
| **M9.5** | Structured Extraction & Aggregation | ✅ |
| **M10** | Deployment & Distribution | ✅ |
| **M11** | Admin Panel, File Management & User Context | ✅ |
| **M12** | Multi-User Support with Authentication | ✅ |
| **M12.5** | AI Pause/Resume, Tag-Based Routing, Private Deploy | ✅ |
| **M12.6** | Admin Improvements, Rescan, Reclassify-All | ✅ |
| **M12.7** | Multi-Page Image Sequences, Reliability | ✅ |

### What M1-M12 Delivers

- File watching with deduplication (xxhash + SHA-256)
- PDF text extraction (PyMuPDF) with OCR fallback (Tesseract)
- Chunking (1500 chars, 200 overlap)
- FTS5 keyword search + vector semantic search + hybrid RRF
- REST API (FastAPI) on port 8000
- CLI (Typer): `init`, `serve`, `config`, `version`, `backup`, `users`
- MCP Server with 13 tools for Claude Desktop / OpenClaw integration
- Web UI for documents, search, tags, upload
- Admin Panel for settings, backup, MCP tokens, users, queue, logs
- First-run wizard for user setup
- Authentication: JWT tokens, bcrypt passwords, optional auth mode
- Auth enforcement: `AuthMiddleware` on admin + write ops; 401 JSON (API) / 302 redirect (UI)
- Web UI login: `/ui/login` page, nav bar shows user/sign-out or sign-in button
- Document ownership: `uploaded_by_user_id`, `document_frequency`, `time_period`
- User-aware classification/extraction: `user:Name` tags, `document_frequency` detection
- 202+ tests passing

### What M12.5 Delivers (2026-02-25)

- **AI processing pause/resume**: Admin console button to pause/resume LLM tasks (classify, embed, extract_metadata). Non-AI tasks (ingest, route_file) continue while paused.
- **Tag-based file routing**: After classification, files are moved to tag-matched subdirectories. `RoutingRule` model with `tags`, `match_mode` (any/all), `priority`, `sub_levels` (template strings supporting `{tag:prefix}`, `{year}`). `ROUTE_FILE` task type runs even when AI is paused. Admin UI at `/ui/admin/routing`.
- **Private deployment script**: `scripts/deploy-private.sh` + `docker-compose.private.yml` for a personal instance on a configurable port (default 8002). Mounts `LIBRARY_PATH` (inbox + archive) and `./data` separately. MCP HTTP port on 8003.
- **Serbian/Croatian OCR**: Added `srp` and `hrv` Tesseract language packs to Docker image.

### What M12.6 Delivers (2026-03-01 – 2026-03-15)

- **Background directory rescan**: Admin watch-folders page gains a "Rescan" button that re-scans a watched directory and queues any new files found.
- **Reclassify-all / Reextract-all**: Admin endpoints and buttons to re-run classification or extraction on all documents in bulk.
- **Configurable LLM timeout**: `llm.timeout` config key (default 300s) passed through to all LLM requests.
- **File reconciliation task**: Maintenance task that checks all document `current_path` values are still valid and logs mismatches.
- **Collapsible PDF preview**: Document detail page shows a collapsible inline PDF viewer.
- **Click-to-edit document title**: Inline editable title on the document detail page.
- **Local timezone display**: All timestamps in the UI are shown in the browser's local timezone (not UTC).
- **Restart button**: Admin settings page gains a server restart button.

### What M12.7 Delivers (2026-03-24 – 2026-03-28)

- **Multi-page image sequences**: Scanner files following the pattern `img-[id]-001.jpg`, `img-[id]-002.jpg`, … are automatically grouped into a single document. The canonical page (001) is hashed for deduplication; all sibling pages are stored as `page_images` (JSON array on the `Document` model). OCR is run page-by-page in order with a unified chunk index. The document detail page shows a pageable gallery (Alpine.js `page`/`total` state, `←Prev / Next→` controls) served via `GET /api/v1/documents/{id}/page-image/{index}`.
- **Demo deployment isolation**: `deploy-demo.sh` and `deploy-demo-fast.sh` now use a named Docker volume (`mymemex-demo-data`) instead of a bind mount to `./data`. Neither script loads `.env` or the real LLM provider, so the demo instance is completely isolated from real user data.
- **SQLite lock retry**: When bulk-ingesting large libraries (400+ files), concurrent workers could hit `SQLITE_BUSY` ("database is locked"). A Python-level retry loop (`_process_task_with_retry`) catches `OperationalError: database is locked` and retries up to 6 times with exponential backoff (0.5 s → 30 s cap) + random jitter before counting the failure against the task's retry budget. `PRAGMA busy_timeout` also corrected from 30 s to 60 s to match the `connect_args` timeout.
- **Chunk deduplication on reprocess**: `run_ingest_pipeline` now calls `chunk_repo.delete_by_document()` before re-creating chunks, preventing duplicate rows when a document is reprocessed.

### Specs for Completed Milestones

- [MCP-SPEC.md](MCP-SPEC.md) — M7 MCP Server
- [M11-SPEC.md](M11-SPEC.md) — M11 Admin Panel

---

## Upcoming Milestones

### M13: Chat Interface

**Goal:** Optional built-in conversational interface with RAG over the document library.

| Feature | Description | Effort |
|---------|-------------|--------|
| RAG pipeline | Retrieve chunks, generate answers with citations | Medium |
| Chat UI component | Embedded in Web UI | Medium |
| Conversation history | Persist chat sessions | Low |
| Citation links | Link answers to source documents and pages | Medium |
| LLM endpoint config | Separate model for chat (Ollama) | Low |

**Estimated effort:** 1-2 weeks

**Dependencies:** M6 (semantic search), M8 (Web UI)

**Technical approach:** Uses a separate Ollama model for generation (distinct from embedding model). MCP (M7) already provides conversational access for most users; M13 is for users who want a self-contained experience.

**Success criteria:**
- Users can ask natural language questions about their library
- Answers include citations with document + page references
- Chat history is persisted across sessions
- Works with local Ollama models (no cloud requirement)

---

### M14: Cloud OCR Fallback

**Goal:** High-fidelity OCR for difficult documents using cloud APIs, with privacy controls.

| Feature | Description | Effort |
|---------|-------------|--------|
| Cloud OCR adapters | AWS Textract and/or Google Vision | Medium |
| Privacy policies | Per-directory sensitivity flags | Low |
| Auto-fallback | Trigger cloud OCR when local confidence is low | Low |
| Data purge verification | Confirm cloud provider deletes data | Low |

**Estimated effort:** 3-4 days

**Dependencies:** M5 (local OCR). Independent of other milestones.

**Technical approach:** Adapter pattern — `CloudOCRAdapter` with the same interface as local `ocr.py`. Config specifies which directories allow cloud processing.

**Success criteria:**
- Cloud OCR works as fallback when local OCR confidence is below threshold
- Sensitive directories are never sent to cloud
- Cloud provider is configurable (at least one supported)
- Works without cloud credentials (local-only is default)

---

## Dependency Graph

```
M1-M6 (Complete)
    │
    ▼
M6.5 (Service Layer) ✅
    │
    ▼
M7 (MCP Server) ✅
    │
    ├──────────────┐
    ▼              ▼
M8 (Web UI) ✅  M9 (Auto-Tag) ✅
    │              │
    │              ▼
    │         M9.5 (Extraction) ✅
    │              │
    ▼              │
M10 (Deployment) ✅
    │
    ▼
M11 (Admin Panel) ✅
    │
    ├──────────────┐
    ▼              ▼
M12 (Multi-User) M14 (Cloud OCR)
    │            (independent)
    ▼
M13 (Chat Interface)
```

---

## Effort Summary (Remaining)

| Milestone | Effort | Notes |
|-----------|--------|-------|
| M13 Chat Interface | ~1-2 weeks | Optional RAG chat |
| M14 Cloud OCR | ~3-4 days | Independent, can be done anytime |

**Total remaining effort:** ~2-3 weeks for M13-M14.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auth security vulnerabilities | M12 exposure | Use battle-tested libraries (bcrypt, jose), rate limiting |
| ChromaDB multi-user isolation | M12 complexity | Use metadata filtering, not separate collections |
| Cloud OCR cost/privacy | M14 adoption | Strict opt-in, per-directory policies |
| Ollama model availability | M13 blocked | Graceful degradation when LLM unavailable |

---

## Current Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Unit + Integration | 202 | Pass |
| OCR integration | — | Pass (skip if unavailable) |
| Ollama integration | 15 | Skip (requires running Ollama) |

---

## Quick Start

```bash
# Install
pip install mymemex[ocr,ai,mcp]

# Configure
mymemex init
nano ~/.config/mymemex/config.yaml

# Run
mymemex serve

# Open Web UI
open http://localhost:8000/ui

# Search via API
curl "http://localhost:8000/api/v1/search/hybrid?q=insurance"

# Connect Claude Desktop via MCP
# Add to claude_desktop_config.json:
# {"mcpServers": {"mymemex": {"command": "mymemex", "args": ["mcp", "serve"]}}}
```
