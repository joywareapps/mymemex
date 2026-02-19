# MyMemex: Milestones & Roadmap

**Last Updated:** 2026-02-19

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

### What M1-M11 Delivers

- File watching with deduplication (xxhash + SHA-256)
- PDF text extraction (PyMuPDF) with OCR fallback (Tesseract)
- Chunking (1500 chars, 200 overlap)
- FTS5 keyword search + vector semantic search + hybrid RRF
- REST API (FastAPI) on port 8000
- CLI (Typer): `init`, `serve`, `config`, `version`, `backup`
- MCP Server with 13 tools for Claude Desktop / OpenClaw integration
- Web UI for documents, search, tags, upload
- Admin Panel for settings, backup, MCP tokens, users, queue, logs
- First-run wizard for user setup
- 141 tests passing

### Specs for Completed Milestones

- [MCP-SPEC.md](MCP-SPEC.md) — M7 MCP Server
- [M11-SPEC.md](M11-SPEC.md) — M11 Admin Panel

---

## Upcoming Milestones

### M12: Multi-User Support (Auth, Ownership, Visibility)

**Goal:** Full multi-user support with authentication, document ownership, and visibility controls.

| Feature | Description | Effort |
|---------|-------------|--------|
| User authentication | Username/password login with bcrypt | Medium |
| Session management | Secure sessions, logout | Medium |
| Document ownership | Track who uploaded each document | Low |
| Per-folder user association | Assign watch folders to users | Low |
| Visibility flags | Shared vs private documents | Medium |
| Query filtering | "My documents" vs "all documents" | Low |
| MCP user context | Pass user identity through MCP requests | Low |
| Alembic migrations | Schema migrations for production | Medium |

**Estimated effort:** 2-3 weeks

**Dependencies:** M7 (MCP), M11 (User table exists)

**Spec:** See [MULTI-USER-SPEC.md](MULTI-USER-SPEC.md) for design details.

---

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
| M12 Multi-User | ~2-3 weeks | Auth, ownership, visibility |
| M13 Chat Interface | ~1-2 weeks | Optional RAG chat |
| M14 Cloud OCR | ~3-4 days | Independent, can be done anytime |

**Total remaining effort:** ~4-6 weeks for M12-M14.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auth security vulnerabilities | M12 exposure | Use battle-tested libraries (passlib), rate limiting |
| ChromaDB multi-user isolation | M12 complexity | Use metadata filtering, not separate collections |
| Cloud OCR cost/privacy | M14 adoption | Strict opt-in, per-directory policies |
| Ollama model availability | M13 blocked | Graceful degradation when LLM unavailable |

---

## Current Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Unit + Integration | 141 | Pass |
| OCR integration | — | Pass (skip if unavailable) |
| Ollama integration | — | Pass (skip if unavailable) |

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
