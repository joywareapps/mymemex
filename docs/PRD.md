# Project Librarian: Product Requirements Document (PRD)

**Version:** 1.1
**Status:** M1-M8 Complete | Production Ready
**Codename:** Librarian
**Last Updated:** 2026-02-17

---

## 1. Executive Summary

Librarian is a sovereign document intelligence platform designed to transform unstructured personal archives (PDFs, scans, images) into a searchable, agentic database. Unlike cloud-first solutions, Librarian prioritizes privacy by allowing users to toggle between cloud-based high-fidelity models and local, air-gapped LLMs/OCR engines.

**Current State:**
- ✅ Core platform complete (M1-M8)
- ✅ MCP Server for Claude Desktop/OpenClaw integration
- ✅ Web UI for document browsing and management
- ✅ Semantic search with local Ollama embeddings
- 🚧 Auto-tagging and multi-user support planned

---

## 2. System Architecture Overview

The system follows a **"Hybrid Memory"** architecture:

### Components

| Component | Responsibility | Status |
|-----------|----------------|--------|
| **Watcher** | Monitors local/NAS directories for new files | ✅ M3 |
| **Ingestion Worker** | Handles file queuing, hashing (deduplication), metadata extraction | ✅ M3 |
| **Intelligence Core** | Executes OCR (Tesseract) and Embedding generation | ✅ M5, M6 |
| **Storage Layer** | SQLite (metadata/relationships) + ChromaDB (semantic chunks) | ✅ M2, M6 |
| **Service Layer** | Business logic for documents, search, tags, ingest | ✅ M6.5 |
| **MCP Server** | Model Context Protocol for LLM integration | ✅ M7 |
| **Web UI** | Browser-based document management | ✅ M8 |
| **Agentic Layer** | Auto-tagging and autonomous organization | 🔜 M9 |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│  CLI │ Web UI (/ui) │ MCP (Claude/OpenClaw) │ REST API (/api)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER (M6.5)                       │
│  DocumentService │ SearchService │ TagService │ IngestService  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INTELLIGENCE CORE                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Local OCR    │  │ Embedding    │  │ Auto-Tag     │          │
│  │ (Tesseract)  │  │ (Ollama)     │  │ (LLM) 🔜     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                              │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ SQLite           │  │ ChromaDB         │                    │
│  │ (metadata/FTS5)  │  │ (vectors)        │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Watcher  │──│ Deduplication│──│ Task Queue   │              │
│  │          │  │ (xxhash/SHA) │  │ (SQLite)     │              │
│  └──────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Interfaces

### 3.1 Web UI (M8)

Browser-based interface at `http://localhost:8000/ui/`:
- Document list with filters (status, tag, date)
- Search with keyword/semantic/hybrid modes
- Document detail view with content and tags
- Tag management (add/remove)
- Drag-and-drop upload

**Tech:** HTMX + Alpine.js + Tailwind CSS (CDN, no build step)

### 3.2 MCP Server (M7)

Model Context Protocol server for LLM integration:
- **8 Tools:** search_documents, get_document, get_document_text, list_documents, add_tag, remove_tag, upload_document, get_library_stats
- **2 Resources:** library://tags, library://stats
- **2 Prompts:** search_and_summarize, compare_documents

**Clients:** Claude Desktop, OpenClaw, any MCP-compatible client

### 3.3 REST API

FastAPI endpoints at `http://localhost:8000/api/v1/`:
- Documents CRUD
- Search (keyword, semantic, hybrid)
- Tags management
- System status

**Docs:** `http://localhost:8000/docs`

### 3.4 CLI

Command-line interface:
- `librarian init` — Initialize configuration
- `librarian serve` — Start API server
- `librarian config` — Manage configuration
- `librarian mcp serve` — Start MCP server

---

## 4. Features

### 4.1 Intelligent Ingestion & Monitoring ✅

**Real-time Archive Synchronization:**
- File watcher monitors configured directories
- SHA-256 + xxhash deduplication
- Automatic queuing for processing

**Recovery:**
- Stale task recovery on startup (crashed tasks)
- Stuck document recovery (processing without task)

### 4.2 OCR & Text Extraction ✅

**Local-First Processing:**
- Tesseract OCR for scanned documents
- PyMuPDF for text extraction
- Multi-language support (configured: eng+deu)
- OCR audit logging

### 4.3 Semantic Search ✅

**Vector-Powered Discovery:**
- Ollama embeddings (nomic-embed-text)
- ChromaDB vector store
- Hybrid search (keyword + semantic RRF fusion)
- FTS5 full-text search

### 4.4 Agentic Integration ✅

**MCP Interface:**
- Natural language queries via Claude Desktop
- Document Q&A with citations
- Multi-document analysis

---

## 5. Upcoming Features

### M9: Auto-Tagging 🔜
- LLM-based classification on ingest
- Tag suggestions based on content
- Confidence thresholds

### M10: Multi-User Support 📋
- Named profiles
- Document ownership tracking
- Per-user filtering

### M11: Cloud OCR Fallback 📋
- AWS Textract / Google Vision
- Per-directory privacy policies
- Auto-fallback for low confidence

### M12: RAG Chat Interface 📋
- Built-in conversational Q&A
- Citation links
- Chat history

---

## 6. Technical Specifications

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.11+ |
| **API Framework** | FastAPI |
| **Database** | SQLite + FTS5 + ChromaDB |
| **OCR** | Tesseract (via pytesseract) |
| **Embeddings** | Ollama (nomic-embed-text) |
| **Watcher** | watchdog |
| **Queue** | SQLite-backed async queue |
| **MCP** | mcp Python SDK |
| **Web UI** | HTMX + Alpine.js + Tailwind CSS |

---

## 7. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Latency** | Search < 3 seconds (local) |
| **Scalability** | 50,000 documents |
| **Portability** | Single-machine deployment |
| **Hardware** | 16GB RAM minimum |
| **Storage** | ~1GB per 1000 documents |

---

## 8. Milestones

| Milestone | Description | Status | Date |
|-----------|-------------|--------|------|
| **M1** | Project skeleton, config system, CLI | ✅ Complete | 2026-02 |
| **M2** | SQLite database, SQLAlchemy models, migrations | ✅ Complete | 2026-02 |
| **M3** | File watcher, deduplication (SHA-256), task queue | ✅ Complete | 2026-02 |
| **M4** | Text extraction (PyMuPDF), chunking, FTS5 search | ✅ Complete | 2026-02 |
| **M5** | OCR integration (Tesseract) for scanned PDFs | ✅ Complete | 2026-02 |
| **M6** | Vector embeddings + semantic search (Ollama + ChromaDB) | ✅ Complete | 2026-02 |
| **M6.5** | Service layer extraction | ✅ Complete | 2026-02-17 |
| **M7** | MCP Server (8 tools, 2 resources, 2 prompts) | ✅ Complete | 2026-02-17 |
| **M7.5** | OpenClaw skill for Librarian | ✅ Complete | 2026-02-17 |
| **M8** | Web UI (document browser, search, tags, upload) | ✅ Complete | 2026-02-17 |
| **M9** | Auto-tagging with LLM | 🔜 Planned | - |
| **M10** | Multi-user support | 📋 Planned | - |
| **M11** | Cloud OCR fallback | 📋 Planned | - |
| **M12** | RAG chat interface | 📋 Planned | - |
| **M13** | Deployment & distribution | 📋 Planned | - |

---

## 9. Test Coverage

**Current:** 101+ tests passing

| Category | Tests | Status |
|----------|-------|--------|
| Unit tests | 70+ | ✅ Pass |
| OCR integration | 12 | ✅ Pass |
| Ollama integration | 10 | ✅ Pass (skip if unavailable) |
| Semantic E2E | 5 | ✅ Pass (skip if unavailable) |
| Web UI routes | 15 | ✅ Pass |

---

## 10. Known Issues & TODO

See [TODO.md](../TODO.md) for current issues and improvements:

**High Priority:**
- [ ] Show warning when running without config
- [ ] Optimize database lock duration on uploads

**Medium Priority:**
- [ ] Empty state improvements in Web UI
- [ ] CLI `init` should create config file
- [ ] MCP better error messages

---

## 11. Quick Start

```bash
# Install
pip install -e ".[dev,ocr,ai]"

# Initialize
librarian init
nano ~/.config/librarian/config.yaml

# Configure Ollama endpoint
llm:
  provider: ollama
  model: nomic-embed-text
  api_base: http://localhost:11434

# Start
librarian serve

# Access
open http://localhost:8000/ui/
```

---

## 12. References

- [MILESTONES.md](MILESTONES.md) — Detailed roadmap
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical architecture
- [MCP-SPEC.md](MCP-SPEC.md) — MCP server specification
- [MULTI-USER-SPEC.md](MULTI-USER-SPEC.md) — Multi-user design
- [TODO.md](../TODO.md) — Issues and improvements
