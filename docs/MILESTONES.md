# Librarian: Milestones & Roadmap

**Last Updated:** 2026-02-17

---

## Completed Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| **M1** | Project skeleton, config system, CLI | Done |
| **M2** | SQLite database, SQLAlchemy models, migrations | Done |
| **M3** | File watcher, deduplication (SHA-256), task queue | Done |
| **M4** | Text extraction (PyMuPDF), chunking, FTS5 search | Done |
| **M5** | OCR integration (Tesseract) for scanned PDFs | Done |
| **M6** | Vector embeddings + semantic search (Ollama + ChromaDB) | Done |

### What M1-M6 Delivers

- File watching with deduplication (xxhash + SHA-256)
- PDF text extraction (PyMuPDF) with OCR fallback (Tesseract)
- Chunking (1500 chars, 200 overlap)
- FTS5 keyword search + vector semantic search + hybrid RRF
- REST API (FastAPI) on port 8000
- CLI (Typer): `init`, `serve`, `config`, `version`
- 83 tests (68 pass, 15 skip when Ollama/Tesseract unavailable)

---

## Upcoming Milestones

### M6.5: Service Layer Extraction

**Goal:** Extract business logic from API handlers and pipelines into a clean service layer, establishing the shared backend that MCP tools and REST endpoints both call into.

**Priority:** HIGH — Must be completed before M7. The current codebase has business logic scattered across API route handlers, pipeline stages, and repositories. M7 (MCP) requires a well-defined service layer to avoid duplicating logic.

| Feature | Description | Effort |
|---------|-------------|--------|
| `DocumentService` | CRUD, status management, file operations | Medium |
| `SearchService` | Keyword, semantic, hybrid search orchestration | Medium |
| `TagService` | Tag CRUD, bulk operations | Low |
| `IngestService` | Upload handling, pipeline triggering | Low |
| `StatsService` | Library statistics aggregation | Low |
| API handler refactor | Thin REST handlers calling service layer | Medium |

**Estimated effort:** 2-3 days

**Dependencies:** M6 (current codebase must be stable)

**Technical approach:** Create `src/librarian/services/` package with one service class per domain. Each service encapsulates the business logic currently in API handlers (e.g., `routers/documents.py`) and pipeline code. API handlers become thin wrappers that validate input, call a service method, and format the response. Repositories remain as the data-access layer beneath services.

**Architecture:**
```
REST API handlers ──┐
                    ├──→ Service Layer ──→ Repositories ──→ SQLite/ChromaDB
MCP tool handlers ──┘
```

**Success criteria:**
- All business logic lives in `src/librarian/services/`
- REST API handlers contain no business logic (validation + delegation only)
- Existing tests continue to pass
- Service layer is independently testable
- Clear boundary: services own transactions, repositories own queries

**ADR:** See [ARCHITECTURE.md](ARCHITECTURE.md) ADR-008 for design rationale.

---

### M7: MCP Server

**Goal:** Expose Librarian's capabilities via the Model Context Protocol, making the library accessible from Claude Desktop, OpenClaw, and any MCP-compatible client.

**Priority:** HIGH — Primary conversational interface. MCP provides immediate access without building a custom chat UI.

| Feature | Description | Effort |
|---------|-------------|--------|
| MCP tool: `search_documents` | Keyword, semantic, and hybrid search via MCP | Low |
| MCP tool: `get_document` | Retrieve document metadata + content chunks | Low |
| MCP tool: `get_document_text` | Page-range text retrieval for LLM context | Low |
| MCP tool: `list_documents` | Paginated document listing with filters | Low |
| MCP tools: `add_tag`, `remove_tag` | Tag management via MCP | Low |
| MCP tool: `upload_document` | File-path primary, base64 with size limits | Medium |
| MCP tool: `get_library_stats` | Document count, tags, storage usage | Low |
| MCP resources | `library://tags`, `library://stats` (lean set) | Low |
| stdio transport | Local integration (Claude Desktop) | Low |
| HTTP/SSE transport | Remote access with security hardening | Medium |
| MCP prompts | `search_and_summarize`, `compare_documents` | Low |
| Security | Path validation, rate limiting, localhost default | Medium |

**Estimated effort:** 1.5-2 weeks

**Dependencies:** M6.5 (service layer extraction)

**Technical approach:** Use the official `mcp` Python SDK. MCP tools are thin wrappers that call the service layer extracted in M6.5. Security hardening includes path validation for `watch_directory`, upload size limits, rate limiting for HTTP transport, and localhost-only binding by default.

**Success criteria:**
- Claude Desktop can search, browse, and tag documents via MCP
- Both stdio and SSE transports work
- All MCP tools return structured, typed responses
- Security: path boundaries enforced, upload limits respected, rate limiting active
- Librarian still works without MCP (optional add-on)

**Spec:** See [MCP-SPEC.md](MCP-SPEC.md) for full tool/resource definitions.

---

### M8: Web UI

**Goal:** Browser-based interface for searching, browsing, and managing documents.

| Feature | Description | Effort |
|---------|-------------|--------|
| Document browser | List, filter, sort, paginate documents | Medium |
| Search interface | Keyword + semantic search with result highlighting | Medium |
| Document viewer | PDF preview or text view with page navigation | Medium |
| Tag management | Add/remove tags, bulk operations, tag browser | Low |
| Upload interface | Drag & drop file upload | Low |
| Settings panel | Configure watch directories, view system status | Low |
| Responsive design | Works on desktop and tablet | Low |

**Estimated effort:** 3-4 weeks

**Dependencies:** M6.5 (service layer). MCP (M7) is not required but benefits from it being stable.

**Technical approach:** Lightweight frontend (HTMX + Alpine.js or Svelte) served by FastAPI. No built-in chat — users interact conversationally through MCP clients.

**Success criteria:**
- Users can search and browse documents in a browser
- Document viewer shows extracted text by page
- Tag management works (create, assign, remove)
- File upload triggers ingestion pipeline
- Responsive layout works on screens >= 768px

---

### M9: Auto-Tagging

**Goal:** Automatically classify and tag documents based on content using LLM inference.

| Feature | Description | Effort |
|---------|-------------|--------|
| Classification pipeline | LLM-based document categorization on ingest | Medium |
| Tag suggestion | Suggest tags based on content similarity | Medium |
| Confidence thresholds | Only apply auto-tags above configurable threshold | Low |
| Bulk re-tag | Re-classify existing documents with new model | Low |

**Estimated effort:** 1 week

**Dependencies:** M6 (embeddings). Requires a configured LLM endpoint (Ollama).

**Technical approach:** After ingestion, send document summary + first chunks to an LLM (via Ollama) with a classification prompt. Apply suggested tags with `is_auto=True` flag. The existing `document_tags.is_auto` column already supports this.

**Success criteria:**
- New documents receive auto-tags on ingest (when LLM is configured)
- Auto-tags are distinguishable from manual tags (`is_auto` flag)
- Users can adjust confidence threshold in config
- Classification works offline with local Ollama models

---

### M10: Multi-User Support

**Goal:** Shared library with per-user ownership tracking. A family or small team shares one Librarian instance.

| Feature | Description | Effort |
|---------|-------------|--------|
| User profiles | Named profiles (not full auth initially) | Low |
| Document ownership | Track who uploaded each document (`uploaded_by`) | Low |
| Query filtering | "My documents" vs "all documents" | Medium |
| MCP user context | Pass user identity through MCP requests | Low |
| Migration tooling | Assign existing docs to default user | Low |

**Estimated effort:** 2-3 weeks

**Dependencies:** M7 (MCP for user context). Does NOT depend on M8 — multi-user data model and MCP integration work independently of the Web UI. Web UI user-switching is part of M8 or a post-M8 enhancement.

**Technical approach:** Add `users` table and `uploaded_by` column on documents. Named profiles with no authentication for MVP. MCP passes user identity via request context. See [MULTI-USER-SPEC.md](MULTI-USER-SPEC.md) for design details.

**Success criteria:**
- Multiple named profiles can coexist
- Documents can be filtered by owner
- Single-user deployments are unaffected (no mandatory user setup)
- Ownership is tracked on upload (who added the document)

**Spec:** See [MULTI-USER-SPEC.md](MULTI-USER-SPEC.md) for design details.

---

### M11: Cloud OCR Fallback

**Goal:** High-fidelity OCR for difficult documents using cloud APIs, with privacy controls.

| Feature | Description | Effort |
|---------|-------------|--------|
| Cloud OCR adapters | AWS Textract and/or Google Vision | Medium |
| Privacy policies | Per-directory sensitivity flags | Low |
| Auto-fallback | Trigger cloud OCR when local confidence is low | Low |
| Data purge verification | Confirm cloud provider deletes data | Low |

**Estimated effort:** 3-4 days

**Dependencies:** M5 (local OCR). Independent of other milestones.

**Technical approach:** Adapter pattern — `CloudOCRAdapter` with the same interface as the local `ocr.py`. Config specifies which directories allow cloud processing. The existing `ocr.confidence_threshold` config drives the fallback trigger.

**Success criteria:**
- Cloud OCR works as fallback when local OCR confidence is below threshold
- Sensitive directories are never sent to cloud
- Cloud provider is configurable (at least one supported)
- Works without cloud credentials (local-only is default)

---

### M12: Chat Interface

**Goal:** Optional built-in conversational interface with RAG over the document library.

| Feature | Description | Effort |
|---------|-------------|--------|
| RAG pipeline | Retrieve chunks, generate answers with citations | Medium |
| Chat UI component | Embedded in Web UI (M8) | Medium |
| Conversation history | Persist chat sessions | Low |
| Citation links | Link answers to source documents and pages | Medium |
| LLM endpoint config | Separate model for chat (Ollama) | Low |

**Estimated effort:** 1-2 weeks

**Dependencies:** M6 (semantic search), M8 (Web UI for embedding chat component).

**Technical approach:** This is NOT needed for most users — MCP (M7) provides conversational access through external clients. M12 is for users who want a self-contained experience. Uses a separate Ollama model for generation (distinct from the embedding model).

**Success criteria:**
- Users can ask natural language questions about their library
- Answers include citations with document + page references
- Chat history is persisted across sessions
- Works with local Ollama models (no cloud requirement)

---

### M13: Deployment & Distribution

**Goal:** Easy installation and production deployment.

| Feature | Description | Effort |
|---------|-------------|--------|
| Docker image | Multi-stage build, optimized size | Low |
| docker-compose.yml | Full stack (Librarian + Ollama + ChromaDB) | Low |
| Systemd service | Linux daemon with auto-restart | Low |
| Backup/restore | Database + vector store backup tooling | Medium |
| User documentation | Installation guide, configuration reference | Medium |
| Monitoring | Health checks, log aggregation guidance | Low |

**Estimated effort:** 1 week

**Dependencies:** All core features should be stable. Docker/compose files already exist as stubs.

**Success criteria:**
- `docker compose up` starts a working Librarian instance
- Backup/restore works for both SQLite and ChromaDB data
- Documentation covers installation, configuration, and common workflows
- Health endpoint suitable for container orchestration

---

## Dependency Graph

```
M1-M6 (Complete)
    │
    ▼
M6.5 (Service Layer) ──────────────────────────────────┐
    │                                                   │
    ▼                                                   │
M7 (MCP Server) ───────────────────────┐               │
    │                                   │               │
    ├──────────────┐                    │               │
    ▼              ▼                    ▼               ▼
M8 (Web UI)   M9 (Auto-Tag)      M10 (Multi-User)  M11 (Cloud OCR)
    │              │                                (independent)
    │              │
    ▼              │
M12 (Chat) ◄──────┘
    │
    ▼
M13 (Deployment)
```

**Notes:**
- M6.5 (Service Layer) is the prerequisite for M7 — extracts shared business logic
- M11 (Cloud OCR) is independent — can be built at any time after M5
- M9 (Auto-Tag) can start after M7 but benefits from M8 for tag management UI
- M10 (Multi-User) depends on M7 for MCP user context, but NOT on M8. Web UI user-switching integrates as part of M8 or post-M8
- M12 (Chat) needs M8 for embedding the chat component
- M13 (Deployment) should wait until features stabilize

---

## Effort Summary

| Milestone | Effort | Calendar Estimate |
|-----------|--------|-------------------|
| M6.5 Service Layer | ~2-3 days | Week 1 |
| M7 MCP Server | ~1.5-2 weeks | Weeks 1-3 |
| M8 Web UI | ~3-4 weeks | Weeks 3-7 |
| M9 Auto-Tagging | ~1 week | Week 4 (parallel with M8) |
| M10 Multi-User | ~2-3 weeks | Weeks 4-6 (parallel with M8) |
| M11 Cloud OCR | ~3-4 days | Any time (independent) |
| M12 Chat Interface | ~1-2 weeks | Weeks 8-9 |
| M13 Deployment | ~1 week | Week 10 |

**Total estimated effort:** 10-14 weeks for M6.5-M13.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Service layer extraction breaks existing tests | M6.5 delay | Incremental refactoring, run tests after each service |
| MCP SDK instability | M7 delay | Pin SDK version, wrap in thin abstraction |
| Security vulnerabilities in MCP HTTP transport | M7 exposure | Localhost-only default, rate limiting, mandatory TLS for network |
| Ollama model availability | M9, M12 blocked | Graceful degradation when LLM unavailable |
| ChromaDB multi-user isolation | M10 complexity | Use metadata filtering, not separate collections |
| Frontend framework churn | M8 rework | Choose boring tech (HTMX or vanilla JS) |
| Cloud OCR cost/privacy | M11 adoption | Strict opt-in, per-directory policies |

---

## Current Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Unit tests | 56 | Pass |
| OCR integration | 12 | Pass |
| Ollama integration | 10 | Pass (skip if unavailable) |
| Semantic E2E | 5 | Pass (skip if unavailable) |
| **Total** | **83** | 68 pass + 15 skip |

---

## Quick Start

```bash
# Install
cd ~/code/librarian
pip install -e ".[dev,ocr,ai]"

# Configure
librarian init
nano ~/.config/librarian/config.yaml

# Run
librarian serve

# Search via API
curl "http://localhost:8000/api/v1/search/hybrid?q=insurance"

# Search via MCP (after M7)
# Connect Claude Desktop or OpenClaw to librarian's MCP server
```
