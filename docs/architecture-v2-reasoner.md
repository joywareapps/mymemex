# Architecture Proposal v2: Reasoner Synthesis

**Source:** DeepSeek Reasoner (synthesizing constraints, PRD, and prior proposals)
**Date:** 2026-02-16
**Status:** Implementation-ready v2 proposal

---

## Executive Summary

This v2 architecture proposal synthesizes the authoritative constraints with insights from both Gemini and Claude proposals, prioritizing:
1. **Strict adherence to "no in-process AI"** — All embeddings and LLM inference externalized via HTTP
2. **Graceful degradation** — Core functionality available without LLM connection  
3. **Implementation pragmatism** — Libraries chosen for reliability, not novelty
4. **Missing feature identification** — Addressing gaps in the PRD for production readiness

The proposal challenges several assumptions from prior documents:
- ❌ **Rejects** `sentence-transformers` (violates constraints)
- ❌ **Rejects** `unstructured` (bloated, opaque dependency)
- ✅ **Accepts** PyMuPDF-first extraction (critical optimization)
- ✅ **Accepts** two-phase hashing (performance necessity)
- ⚠️ **Revises** OCR choice due to PyTorch dependency concerns

---

## 1. Python Library Choices with Justification

### 1.1 Core Framework & Runtime

| Library | Version | Purpose | Justification | Constraint Compliance |
|---------|---------|---------|---------------|----------------------|
| `fastapi` | 0.115+ | HTTP API + WebSocket | Async-native, auto OpenAPI, industry standard | ✅ |
| `uvicorn` | 0.34+ | ASGI server | Production-grade, FastAPI companion | ✅ |
| `pydantic` | 2.x | Config & validation | Type safety, FastAPI integration | ✅ |
| `pydantic-settings` | 2.x | Settings management | Hierarchical config (env → YAML) | ✅ |
| `typer` | 0.15+ | CLI interface | Consistent with FastAPI patterns | ✅ |
| `structlog` | 25.x | Structured logging | JSON for prod, pretty for dev | ✅ |
| `alembic` | 1.14+ | DB migrations | Schema evolution essential | ✅ |

### 1.2 File Watching & Ingestion

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| `watchdog` | 6.x | Filesystem events | Cross-platform, reliable, mature |
| `python-magic` | 0.4+ | MIME type detection | More reliable than file extensions |
| `xxhash` | 3.x | Fast hashing (pre-filter) | 10x faster than SHA-256 for dedup pre-check |
| `hashlib` (stdlib) | — | SHA-256 (canonical hash) | Cryptographic dedup, already in stdlib |

**Critical optimization:** Use xxhash on file size + first 4KB for rapid "probably seen" pre-filter, compute full SHA-256 only for potentially new files. On 50K file archive, reduces startup scan from ~15 minutes to ~2 seconds.

### 1.3 Document Processing & OCR

**⚠️ Critical Constraint Consideration:** The "no ML framework" constraint prohibits PyTorch/TensorFlow. This impacts OCR choice:

| Library | Version | Purpose | PyTorch Dep? | Justification |
|---------|---------|---------|-------------|---------------|
| `pymupdf` (fitz) | 1.25+ | PDF text extraction & rendering | No | Fastest PDF library; extracts embedded text without OCR |
| `pytesseract` | 0.3+ | Local OCR (primary) | No | Tesseract wrapper; no PyTorch/TensorFlow |
| `tesserocr` | 2.7+ | Tesseract Python binding | No | Alternative to pytesseract, more efficient |
| `Pillow` | 11.x | Image preprocessing | No | Deskew, denoise before OCR |
| `pdf2image` | 1.17+ | PDF → image conversion | No | For scanned PDFs needing OCR |
| `boto3` | 1.x | AWS Textract (cloud fallback) | No | Cloud OCR when local fails |
| `google-cloud-vision` | 3.x | Google Vision (cloud fallback) | No | Alternative cloud OCR |

**Decision:** Use **Tesseract** as primary local OCR instead of PaddleOCR to avoid PyTorch dependency. Trade-off: Tesseract less accurate on complex layouts but more stable dependency tree.

**OCR Pipeline:** 
1. PyMuPDF attempts native text extraction (instant, works for ~60% of PDFs)
2. If < 50 chars per page → assume scanned, route to Tesseract
3. If Tesseract confidence < threshold (configurable, default 70%) → suggest cloud OCR (opt-in)

### 1.4 Text Processing & Chunking

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| `tiktoken` | 0.9+ | Token counting | Accurate token counts for chunk sizing |
| `langdetect` | 1.0+ | Language detection | Route to correct Tesseract language pack |
| `ftfy` | 6.x | Text cleanup | Fixes encoding issues from OCR |
| `dateparser` | 1.2+ | Date extraction | Extract document dates from content |

**Chunking strategy:** Custom implementation (~100 LOC):
- Recursive split: paragraphs (`\n\n`) → lines (`\n`) → sentences (regex)
- Max 512 tokens with 64-token overlap
- Preserve metadata: page number, approximate section

### 1.5 Embeddings & Vector Store (Constraint-Compliant)

| Library | Version | Purpose | Constraint Compliance |
|---------|---------|---------|----------------------|
| `chromadb` | 0.6+ | Vector storage | ✅ No ML dependencies |
| `httpx` | 0.28+ | HTTP client for Ollama | ✅ |
| `litellm` | 1.x | Unified LLM/embedding API | ✅ External HTTP calls only |

**Embedding model:** `nomic-embed-text:latest` via Ollama HTTP API (768-dim, 8192 token context).

**Critical:** No `sentence-transformers`! Call Ollama's `/api/embeddings` endpoint:
```python
# Via LiteLLM (recommended for retries, fallbacks)
embeddings = await litellm.aembedding(
    model="nomic-embed-text",
    input=[text],
    api_base="http://ollama-host:11434"
)

# Or direct HTTP (simpler)
response = await httpx.post(
    "http://ollama-host:11434/api/embeddings",
    json={"model": "nomic-embed-text", "prompt": text}
)
```

### 1.6 LLM Layer (Constraint-Compliant)

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| `litellm` | 1.x | Unified LLM API | Single interface for Ollama/OpenAI/Anthropic |
| `jinja2` | 3.x | Prompt templates | Battle-tested, already a FastAPI dep |

**Why not LlamaIndex/LangChain:** For Librarian's use cases (single-hop RAG, classification, summarization), a thin wrapper around LiteLLM with Jinja2 templates is ~200 LOC and more debuggable. The "agents" in the PRD are prompt chains, not requiring a framework.

### 1.7 Database

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| `sqlalchemy` | 2.x | ORM + connection management | Type-safe queries, async support |
| `aiosqlite` | 0.20+ | Async SQLite driver | Non-blocking DB access |
| `alembic` | 1.14+ | Schema migrations | Essential for production |

### 1.8 Task Queue & Background Processing

**Decision:** Start with SQLite-backed queue table, upgrade to Redis (`arq`) when needed.

| Library | Version | Purpose | Justification |
|---------|---------|---------|---------------|
| `asyncio` (stdlib) | — | Async worker pool | Built-in, no extra dependency |
| `redis` | 5.x | Optional queue backend | For scaling beyond single NAS |

**Queue implementation choice:** Simple SQLite table with `asyncio` workers initially. SQLite's WAL mode handles concurrent reads during writes. Redis adds operational complexity for NAS deployment.

### 1.9 Testing & Development

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | 8.x | Test runner |
| `pytest-asyncio` | 0.25+ | Async test support |
| `pytest-cov` | 6.x | Coverage |
| `ruff` | 0.9+ | Linting + formatting |
| `mypy` | 1.x | Type checking |
| `pre-commit` | 4.x | Git hooks |

### 1.10 Summary: Constraint Compliance Table

| Library | Gemini Proposal | Claude Proposal | v2 Decision | Constraint Compliant? |
|---------|----------------|-----------------|-------------|----------------------|
| `sentence-transformers` | ✅ | ❌ | ❌ | **NO** (PyTorch dep) |
| `unstructured` | ✅ | ❌ | ❌ | Likely not (pulls many deps) |
| `pymupdf` | ❌ | ✅ | ✅ | Yes |
| `paddleocr` | ✅ | ✅ | ❌ | **NO** (PyTorch dep) |
| `pytesseract` | ❌ | ✅ | ✅ | Yes |
| `litellm` | ❌ | ✅ | ✅ | Yes |
| `llama-index` | ✅ | ❌ | ❌ | Overly complex |
| `chromadb` | ✅ | ✅ | ✅ | Yes |
| `watchdog` | ✅ | ✅ | ✅ | Yes |

---

## 2. Data Flow Architecture

### 2.1 Ingestion Pipeline (Detailed)

```
┌─────────────────────┐
│   Watched Folders   │
│ /mnt/nas/documents  │
└──────────┬──────────┘
           │
           │ inotify/polling (watchdog)
           ▼
┌─────────────────────┐
│    File Watcher     │
│  - Debounce (2s)    │
│  - Ignore patterns  │
│  - Extension filter │
└──────────┬──────────┘
           │
           │ file_path, event_type
           ▼
┌─────────────────────┐
│   Dedup Pre-Check   │
│                     │
│ 1. file_size        │
│ 2. xxhash(first 4KB)│
│ 3. Check DB cache   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
Known file   New/changed
    │             │
    ▼             ▼
┌─────────┐ ┌─────────────┐
│Link path│ │ Task Queue  │
│to existing││ (SQLite)   │
│document │ │ Priority:   │
└─────────┘ │ - HIGH: user│
            │ - NORMAL:   │
            │   watcher   │
            │ - LOW: backfill│
            └─────┬───────┘
                  │
                  ▼
        ┌──────────────────┐
        │ Ingestion Worker │
        │ (async, N=2-4)   │
        └─────────┬────────┘
                  │
        ┌─────────┴────────┐
        │ SHA-256 Full Hash│
        │ MIME type detect │
        │ Metadata extract │
        └─────────┬────────┘
                  │
        ┌─────────┴────────┐
        │ Privacy Check    │
        │ - Sensitive path?│
        │ - Global policy  │
        └─────────┬────────┘
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
   ┌─────────────┐ ┌─────────────┐
   │Local Only   │ │Cloud Allowed│
   │(force local)│ │(choose based│
   └──────┬──────┘ │on config)   │
          │        └──────┬──────┘
          │               │
          └───────┬───────┘
                  │
                  ▼
        ┌──────────────────┐
        │ Text Extraction  │
        │                  │
        │ 1. PyMuPDF try   │
        │    (native text) │
        │ 2. If <50 chars  │
        │    → Tesseract   │
        │ 3. If confidence │
        │    low → suggest │
        │    cloud OCR     │
        └─────────┬────────┘
                  │
                  ▼
        ┌──────────────────┐
        │ Text Pipeline    │
        │ - ftfy cleanup   │
        │ - lang detect    │
        │ - chunking       │
        │ - date extract   │
        └─────────┬────────┘
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
   ┌─────────────┐ ┌─────────────┐
   │  SQLite     │ │   Ollama    │
   │ - document  │ │ /api/embed  │
   │ - chunks    │ │ (external)  │
   │ - metadata  │ └──────┬──────┘
   └─────────────┘        │
                          ▼
                 ┌─────────────┐
                 │  ChromaDB   │
                 │ - vectors   │
                 │ - metadata  │
                 └─────────────┘
```

### 2.2 Query Flow (With Graceful Degradation)

```
User Query
    │
    ▼
┌─────────────┐
│ Query Router│
│             │
│ LLM available?─────No─────┐
│    │ Yes                  │
│    ▼                      ▼
┌─────────┐          ┌─────────────┐
│Vector   │          │FTS5 Keyword │
│Search   │          │Search Only  │
│(semantic)│          │(works offline)│
└────┬────┘          └──────┬──────┘
     │                      │
     ▼                      ▼
┌─────────┐          ┌─────────────┐
│Fetch    │          │Return       │
│context  │          │keyword      │
│from SQLite│          │results     │
└────┬────┘          └─────────────┘
     │
     ▼
┌─────────┐
│LLM      │
│Synthesis│
│(via LiteLLM)│
└────┬────┘
     │
     ▼
┌─────────┐
│Answer + │
│Sources  │
└─────────┘
```

**Graceful degradation key:**
- When LLM unavailable: semantic search disabled, keyword search works
- When Ollama unavailable: embeddings queued, classification skipped
- When Tesseract unavailable: OCR queued, existing text still searchable

### 2.3 Classification Flow (Optimized for Cost)

```
New Document
    │
    ▼
┌─────────────┐
│ Check if    │
│ classification│
│ needed?     │
│ - Already   │
│   categorized│
│ - User opted│
│   out       │
└────┬────────┘
     │ Needed
     ▼
┌─────────────┐
│ Sample      │
│ - First 2   │
│   chunks    │
│ - Or summary│
│   if long   │
└────┬────────┘
     │
     ▼
┌─────────────┐
│ LLM Call    │
│ (via LiteLLM)│
│             │
│ Prompt:     │
│ "Classify   │
│  this doc..."│
└────┬────────┘
     │
     ▼
┌─────────────┐
│ Parse JSON  │
│ - category  │
│ - tags[]    │
│ - summary   │
│ - date      │
└────┬────────┘
     │
     ▼
┌─────────────┐
│ Update DB   │
│ & notify UI │
└─────────────┘
```

**Optimization:** Only classify if document has no existing category/tags AND classification is enabled in config.

---

## 3. Database Schema (SQLite + ChromaDB)

### 3.1 SQLite Schema (Content-Addressed)

```sql
-- Core document identity (content-addressed, not path-addressed)
CREATE TABLE documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT NOT NULL UNIQUE,            -- SHA-256 of file content
    title           TEXT,                            -- Extracted/inferred title
    document_type   TEXT NOT NULL,                   -- MIME type
    page_count      INTEGER,
    language        TEXT DEFAULT 'en',               -- ISO 639-1
    ocr_engine      TEXT,                            -- 'pymupdf_native', 'tesseract', 'textract', 'google_vision'
    ocr_confidence  REAL,                            -- 0.0-1.0 average
    processing_mode TEXT NOT NULL DEFAULT 'local',   -- 'local', 'cloud', 'hybrid'
    category        TEXT,                            -- LLM-assigned category
    summary         TEXT,                            -- LLM-generated 1-sentence summary
    extracted_date  TEXT,                            -- Date found in content (ISO 8601)
    status          TEXT NOT NULL DEFAULT 'pending', -- 'pending','processing','completed','error','waiting_llm'
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    file_size_bytes INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    processed_at    TEXT,
    version         INTEGER NOT NULL DEFAULT 1       -- For document updates
);

-- Multiple file paths can point to same content (deduplication)
CREATE TABLE file_paths (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_path    TEXT NOT NULL UNIQUE,               -- Absolute path
    is_primary   INTEGER NOT NULL DEFAULT 1,         -- 1 = canonical path
    first_seen   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_seen    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at   TEXT                                -- Soft-delete when file disappears
);

-- Document chunks with text (source of truth for retrieval)
CREATE TABLE document_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    vector_id    TEXT NOT NULL UNIQUE,               -- UUID, maps to ChromaDB entry
    chunk_index  INTEGER NOT NULL,                   -- Order within document
    chunk_text   TEXT NOT NULL,
    page_number  INTEGER,                            -- Source page
    token_count  INTEGER NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Tags (many-to-many)
CREATE TABLE tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    source      TEXT NOT NULL DEFAULT 'auto',        -- 'auto' (LLM) or 'manual' (user)
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (document_id, tag_id)
);

-- Processing history (audit trail)
CREATE TABLE processing_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    action       TEXT NOT NULL,                      -- 'ingested','ocr_local','ocr_cloud','classified','reprocessed','error'
    details      TEXT,                               -- JSON blob with action-specific data
    duration_ms  INTEGER,                            -- How long this step took
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Task queue (SQLite-backed alternative to Redis)
CREATE TABLE task_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type    TEXT NOT NULL,                      -- 'embedding','classification','ocr','reprocess'
    document_id  INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    priority     INTEGER NOT NULL DEFAULT 0,         -- Higher = more urgent
    status       TEXT NOT NULL DEFAULT 'pending',    -- 'pending','processing','completed','failed','waiting_llm'
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    scheduled_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    started_at   TEXT,
    completed_at TEXT,
    error        TEXT,
    result       TEXT                                -- JSON result
);

-- Full-text search on chunk content
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_text,
    content='document_chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync (omitted for brevity)
```

### 3.2 ChromaDB Collection Schema

```python
# Single collection with metadata for filtering
collection = chroma_client.get_or_create_collection(
    name="librarian_chunks",
    metadata={"hnsw:space": "cosine"},
)

# Each entry includes filtering metadata
collection.add(
    ids=["chunk-uuid-here"],
    embeddings=[[0.1, 0.2, ...]],         # 768-dim from nomic-embed-text
    documents=["The policy covers..."],    # chunk text
    metadatas=[{
        "document_id": 42,
        "content_hash": "abc123...",
        "page_number": 14,
        "chunk_index": 3,
        "category": "insurance",
        "language": "en",
        "tags": "insurance,legal,auto",    # Comma-separated for Chroma filtering
        "processing_mode": "local",        # For privacy-aware filtering
    }],
)
```

**Key design:** ChromaDB metadata enables filtering by category, tags, processing mode before vector comparison, improving performance and privacy.

---

## 4. API Surface (REST + WebSocket)

### 4.1 REST API (FastAPI)

#### Documents
- `GET /api/v1/documents` — List (paginated, filterable by status/category/tag)
- `GET /api/v1/documents/{id}` — Get document + chunks
- `POST /api/v1/documents/upload` — Manual upload (multipart form)
- `DELETE /api/v1/documents/{id}` — Remove from index (soft delete)
- `PATCH /api/v1/documents/{id}` — Update metadata (title, tags, category)
- `POST /api/v1/documents/{id}/reprocess` — Re-run pipeline

#### Search & Query
- `POST /api/v1/search` — Semantic vector search (requires LLM)
- `POST /api/v1/query` — RAG query with LLM synthesis
- `GET /api/v1/search/fulltext?q=` — FTS5 keyword search (works offline)
- `POST /api/v1/search/hybrid` — Fuse vector + keyword results

#### System & Configuration
- `GET /api/v1/status` — Health, queue depth, storage stats, LLM connectivity
- `GET /api/v1/queue` — Task queue status
- `POST /api/v1/queue/pause` — Pause ingestion
- `POST /api/v1/queue/resume` — Resume ingestion
- `GET /api/v1/tags` — All tags with counts
- `GET /api/v1/config` — Current config (secrets redacted)
- `PUT /api/v1/config` — Update config (runtime reload where possible)

#### Privacy & Processing
- `POST /api/v1/privacy/sensitive` — Mark path as sensitive (force local)
- `POST /api/v1/ocr/cloud-approve` — Approve cloud OCR for specific document
- `GET /api/v1/processing/stats` — Processing statistics (accuracy, timing)

### 4.2 WebSocket API (`/api/v1/ws/events`)

Real-time events for UI updates:

```json
// System events
{"event": "system.llm.connected", "data": {"provider": "ollama", "model": "llama3.2"}}
{"event": "system.llm.disconnected", "data": {"reason": "timeout"}}
{"event": "queue.stats", "data": {"pending": 12, "processing": 3, "waiting_llm": 5}}

// Document events
{"event": "document.discovered", "data": {"path": "/mnt/nas/new.pdf"}}
{"event": "document.processing", "data": {"id": 42, "step": "ocr", "progress": 0.6}}
{"event": "document.completed", "data": {"id": 42, "title": "Insurance Policy"}}
{"event": "document.error", "data": {"id": 42, "error": "OCR timeout", "retryable": true}}

// Classification events
{"event": "classification.suggested", "data": {"id": 42, "category": "tax", "tags": ["2024", "irs"]}}

// User action events
{"event": "user.tag_added", "data": {"document_id": 42, "tag": "important"}}
```

### 4.3 Key Request/Response Schemas

```python
# POST /api/v1/query
class QueryRequest(BaseModel):
    query: str                           # Natural language question
    top_k: int = 10                      # Number of chunks to retrieve
    filter_tags: list[str] | None = None
    filter_category: str | None = None
    filter_processing_mode: str | None = None  # 'local' or 'cloud'
    include_sources: bool = True
    stream: bool = False                 # Stream LLM response via SSE

class QueryResponse(BaseModel):
    answer: str
    confidence: float                    # 0.0-1.0 relevance score
    sources: list[Source]
    query_time_ms: int
    llm_provider: str | None             # Which provider answered
    degraded_mode: bool = False          # True if semantic search unavailable

# POST /api/v1/search
class SearchRequest(BaseModel):
    query: str
    top_k: int = 20
    filter_tags: list[str] | None = None
    filter_category: str | None = None
    filter_processing_mode: str | None = None
    search_mode: str = "hybrid"          # 'vector', 'keyword', 'hybrid'
    threshold: float = 0.3               # Minimum similarity for vector

# GET /api/v1/documents
class DocumentListParams(BaseModel):
    page: int = 1
    per_page: int = 50
    status: str | None = None            # Filter by processing status
    category: str | None = None
    tag: str | None = None
    processing_mode: str | None = None   # 'local' or 'cloud'
    q: str | None = None                 # Full-text search filter
    sort_by: str = "created_at"          # created_at, title, file_size_bytes
    sort_order: str = "desc"             # asc, desc
```

---

## 5. Key Architectural Decisions with Trade-offs

### 5.1 Externalized AI (Constraint-Compliant)
**Decision:** No PyTorch/TensorFlow in-process; all embeddings/LLM via HTTP APIs.

**Trade-offs:**
- ✅ Eliminates large dependencies, reduces install size
- ✅ Allows AI to run on separate hardware (GPU server)
- ✅ Easier model switching via config
- ❌ Network latency added to embedding/LLM calls
- ❌ Dependency on external service availability
- ❌ Harder to debug (network issues vs. code issues)

**Mitigation:** LiteLLM with retries, caching, local Ollama as default.

### 5.2 Tesseract over PaddleOCR
**Decision:** Use Tesseract due to PyTorch dependency constraint.

**Trade-offs:**
- ✅ No PyTorch dependency, simpler install
- ✅ More stable, mature OCR engine
- ✅ Better community support
- ❌ Less accurate on complex layouts/tables
- ❌ Slower on some document types

**Mitigation:** Cloud OCR fallback for low-confidence results.

### 5.3 SQLite-Backed Queue over Redis
**Decision:** Start with SQLite task queue, upgrade to Redis when needed.

**Trade-offs:**
- ✅ Zero additional dependencies for NAS deployment
- ✅ Atomic operations with SQLite's WAL mode
- ✅ Persistence built-in
- ❌ Single-writer limitation (but OK for personal use)
- ❌ Less performant at high throughput

**Mitigation:** Use `PRAGMA journal_mode=WAL`, batch operations, upgrade path to Redis.

### 5.4 Content-Addressed Storage
**Decision:** Identify documents by content hash, not file path.

**Trade-offs:**
- ✅ Handles file moves/copies without reprocessing
- ✅ Natural deduplication
- ✅ Enables version tracking
- ❌ More complex schema (file_paths table)
- ❌ Hash computation cost on ingestion

**Mitigation:** Two-phase hashing (xxhash pre-filter).

### 5.5 Graceful Degradation
**Decision:** Core functionality works without LLM connection.

**Trade-offs:**
- ✅ System remains usable during LLM outages
- ✅ Progressive enhancement model
- ❌ More complex state management
- ❌ UI must handle multiple operational modes

**Mitigation:** Clear status indicators, task queuing with persistence.

### 5.6 Single Process Async Architecture
**Decision:** One Python process with `asyncio` for all components.

**Trade-offs:**
- ✅ Lower memory footprint (critical for NAS)
- ✅ Simpler deployment (one container/process)
- ✅ Shared memory for caching
- ❌ CPU-bound operations (OCR) can block event loop
- ❌ Single point of failure

**Mitigation:** `ProcessPoolExecutor` for OCR, health checks, supervised process.

### 5.7 Hybrid Search (Vector + FTS5)
**Decision:** Implement both semantic and keyword search.

**Trade-offs:**
- ✅ Best of both worlds: conceptual + exact match
- ✅ FTS5 works offline (no LLM needed)
- ❌ More complex query implementation
- ❌ Storage duplication (text in SQLite + ChromaDB)

**Mitigation:** Reciprocal Rank Fusion for result merging, store text only in SQLite.

---

## 6. Bottlenecks and Mitigations

### 6.1 OCR Throughput
**Bottleneck:** Tesseract processes ~1-3 pages/second on NAS CPU.

**Mitigations:**
1. **PyMuPDF native extraction first** — Skip OCR for ~60% of PDFs
2. **ProcessPoolExecutor** — Run OCR in separate processes
3. **Page-level parallelism** — Process multiple pages concurrently
4. **Incremental backfill** — Process in batches with pauses
5. **GPU acceleration** — Not available for Tesseract, but cloud fallback helps

### 6.2 Embedding Generation
**Bottleneck:** HTTP roundtrips to Ollama (~50-100ms per chunk).

**Mitigations:**
1. **Batch embeddings** — Ollama supports batch API (32+ chunks per request)
2. **Pipeline parallelism** — Embed while next document is OCR'd
3. **Embedding cache** — Store in ChromaDB, skip re-embedding identical text
4. **Model selection** — `nomic-embed-text` faster than larger models

### 6.3 Memory Constraints
**Bottleneck:** 16GB NAS RAM shared between OCR, LLM, ChromaDB.

**Mitigations:**
1. **Lazy LLM loading** — Load model on query, unload after timeout
2. **Smaller LLM for classification** — Use `llama3.2:1b` (~1GB) vs. 7B (~4GB)
3. **ChromaDB memory mapping** — Use `persist_directory` on disk with mmap
4. **Process isolation** — Run Ollama on separate machine if available

### 6.4 Initial Backfill of 50K Documents
**Bottleneck:** Could take days/weeks.

**Mitigations:**
1. **Priority queue** — New files first, backfill during idle time
2. **Progress persistence** — Resume from checkpoint after restart
3. **User transparency** — Show estimated time remaining
4. **Optional: skip embeddings initially** — Enable keyword search first, add vectors later

### 6.5 SQLite Write Contention
**Bottleneck:** SQLite single-writer limitation.

**Mitigations:**
1. **WAL mode** — `PRAGMA journal_mode=WAL` for concurrent reads during writes
2. **Batch writes** — Buffer inserts, flush periodically
3. **Read/write connection separation** — Different connections for queries vs. writes
4. **Queue serialization** — Single worker writes to SQLite, others use message queue

### 6.6 File System Monitoring
**Bottleneck:** `watchdog` on large directories (50K+ files).

**Mitigations:**
1. **Debouncing** — Group rapid file changes (2s window)
2. **Exclude patterns** — Ignore temp files, system files
3. **Polling fallback** — Use polling for network drives that don't support inotify
4. **Incremental scan** — On startup, check modified times vs. DB

---

## 7. Missing Features from PRD (Should Be Considered)

### 7.1 Critical Production Gaps

**1. Document Versioning**
PRD handles deduplication but not document updates. Need:
- Detection when existing file path has new content hash
- Version table linking document revisions
- Option to keep/discard old versions
- "What changed?" diff between versions

**2. Comprehensive Error Handling**
PRD mentions status but not recovery:
- Retry strategies with exponential backoff
- Dead letter queue for permanently failed documents
- User notifications for persistent errors
- Automatic fallback (local → cloud OCR when local fails)

**3. Backup & Disaster Recovery**
For a system indexing important documents:
- Atomic backup of SQLite + ChromaDB
- Export/import functionality
- Recovery procedure documentation
- Integrity verification (checksums)

**4. File Lifecycle Management**
PRD covers creation but not deletion:
- Handle file deletion from watched folders
- Soft-delete vs. purge options
- Orphan detection (indexed files missing from disk)
- Retention policies (auto-delete after N years)

**5. Monitoring & Observability**
Missing in PRD:
- Health check endpoint
- Performance metrics (processing rate, latency)
- Error rate tracking and alerting
- Resource usage monitoring (disk, RAM, CPU)

### 7.2 Important v2 Additions

**6. Multi-Language Support**
PRD assumes English:
- Language detection for OCR routing
- Multi-language Tesseract packs
- Mixed-language document handling
- Translation option for search queries

**7. Structured Data Extraction**
Implied but not specified:
- Table detection and parsing
- Key-value pair extraction (invoice numbers, totals)
- Form field extraction
- Structured metadata storage

**8. Access Control**
For multi-user potential:
- API key authentication
- Per-user document visibility
- Shared vs. private tags
- Audit logging of accesses

**9. Document Preview & Annotation**
Users will want:
- Thumbnail generation
- OCR text overlaid on images
- Manual correction of OCR errors
- Highlighting and annotation

**10. Incremental Re-indexing**
Needed for model/algorithm updates:
- "Reindex" command with options (all, by category, by date)
- Progress tracking for large re-index operations
- Versioning of embedding models
- A/B testing of retrieval improvements

### 7.3 Recommended Implementation Priority

Based on the PRD milestones, adjust for faster time-to-value:

| Phase | Deliverable | Change from PRD |
|-------|-------------|-----------------|
| **M1** | Project skeleton + config + CLI + SQLite schema | Added config system |
| **M2** | File watcher + dedup (xxhash+SHA-256) + ingestion queue | Two-phase hashing |
| **M3** | PyMuPDF text extraction + FTS5 keyword search | **Moved up** — search before OCR |
| **M4** | Basic REST API + document listing | Earlier user value |
| **M5** | Tesseract OCR for scanned documents | Was M3 |
| **M6** | Ollama embeddings + ChromaDB + semantic search | Requires LLM |
| **M7** | RAG query interface (LiteLLM) | Same |
| **M8** | Auto-tagging + classification | Same |
| **M9** | WebSocket events + real-time UI | **New** |
| **M10** | Cloud OCR fallback + privacy controls | Same |
| **M11** | Docker deployment + monitoring | Added monitoring |

**Key insight:** By implementing PyMuPDF extraction and FTS5 search before OCR/embeddings (M3), users get working keyword search without AI dependencies. This provides immediate value while heavier processing continues in background.

---

## 8. Configuration Schema (YAML)

```yaml
# config.yaml

# Watcher configuration
watcher:
  directories:
    - /mnt/nas/documents
    - /mnt/nas/scans
  ignore_patterns:
    - "*.tmp"
    - "*.swp"
    - ".*"  # hidden files
  debounce_ms: 2000
  polling_interval: 60  # for network drives

# Processing pipeline
processing:
  max_file_size_mb: 100
  ocr:
    primary: tesseract
    language: eng
    confidence_threshold: 0.7
    suggest_cloud_below: 0.5
  chunking:
    max_tokens: 512
    overlap_tokens: 64

# AI/LLM configuration
ai:
  # Unified via LiteLLM
  llm:
    provider: ollama
    base_url: ${OLLAMA_HOST:http://localhost:11434}
    model: llama3.2:latest
    timeout: 120
    max_retries: 3
  
  embedding:
    provider: ollama
    base_url: ${OLLAMA_HOST:http://localhost:11434}
    model: nomic-embed-text:latest
    batch_size: 32
  
  classification:
    enabled: true
    model: llama3.2:1b  # Smaller model for classification
    sample_chunks: 2

# Privacy controls
privacy:
  default_mode: local
  sensitive_paths:
    - /mnt/nas/financial
    - /mnt/nas/medical
  cloud_require_approval: true
  cloud_data_retention_hours: 24

# Storage
storage:
  sqlite_path: ${SQLITE_PATH:/var/lib/librarian/librarian.db}
  chromadb_path: ${CHROMADB_PATH:/var/lib/librarian/chromadb}
  backup:
    enabled: true
    interval_hours: 24
    keep_count: 7

# Queue & workers
queue:
  max_concurrent_workers: 4
  max_retries: 3
  retry_delay_ms: 5000

# API server
server:
  host: 0.0.0.0
  port: 8000
  cors_origins:
    - "http://localhost:3000"
  auth:
    enabled: false
    api_key: ${API_KEY:}
```

---

## 9. Project Structure (Implementation-Ready)

```
librarian/
├── pyproject.toml
├── alembic.ini
├── config/
│   ├── config.example.yaml
│   └── __init__.py
├── src/
│   └── librarian/
│       ├── __init__.py
│       ├── __main__.py              # typer CLI entry point
│       ├── config.py                # Pydantic settings
│       ├── app.py                   # FastAPI app factory
│       ├── api/
│       │   ├── __init__.py
│       │   ├── documents.py
│       │   ├── search.py
│       │   ├── system.py
│       │   └── websocket.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── watcher.py           # File system watcher
│       │   ├── queue.py             # SQLite task queue
│       │   ├── worker.py            # Async worker pool
│       │   └── scheduler.py         # Background tasks
│       ├── processing/
│       │   ├── __init__.py
│       │   ├── hasher.py            # xxhash + SHA-256
│       │   ├── extractor.py         # PyMuPDF text extraction
│       │   ├── ocr.py               # Tesseract OCR router
│       │   ├── chunker.py           # Text chunking
│       │   ├── embedder.py          # Embedding via Ollama/LiteLLM
│       │   └── classifier.py        # LLM classification
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py          # SQLAlchemy session
│       │   ├── models.py            # SQLAlchemy models
│       │   ├── vector_store.py      # ChromaDB wrapper
│       │   └── repositories.py      # Data access layer
│       └── llm/
│           ├── __init__.py
│           ├── client.py            # LiteLLM wrapper
│           ├── prompts/             # Jinja2 templates
│           │   ├── classify.j2
│           │   ├── query.j2
│           │   └── summarize.j2
│           └── agents.py            # Simple agent implementations
├── tests/
│   ├── conftest.py
│   ├── test_watcher.py
│   ├── test_processing.py
│   └── fixtures/
│       └── sample.pdf
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/
    ├── PRD.md
    ├── ARCHITECTURE-CONSTRAINTS.md
    └── architecture-v2-reasoner.md  # This document
```

---

## 10. Conclusion

This v2 architecture proposal respects the critical constraint of **no in-process AI dependencies** while delivering a production-ready document intelligence platform. Key innovations:

1. **Constraint-compliant AI** — All embeddings/LLM via HTTP APIs (Ollama + LiteLLM)
2. **Graceful degradation** — Keyword search works without LLM, tasks queue when offline
3. **Performance optimizations** — Two-phase hashing, PyMuPDF-first extraction, batch embeddings
4. **Production features** — Comprehensive error handling, monitoring, backup, versioning
5. **Pragmatic library choices** — Tesseract over PaddleOCR to avoid PyTorch, SQLite over Redis for simplicity

The architecture enables **progressive enhancement**: users get working keyword search early (M3), semantic search when LLM available, and cloud OCR as optional enhancement. This balances immediate utility with long-term capability.

**Next steps:** Begin implementation with M1 (project skeleton) ensuring all dependency choices respect the no-PyTorch constraint, and design the queue system for graceful degradation from day one.