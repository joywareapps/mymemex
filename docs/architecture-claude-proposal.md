# Architecture Proposal: Claude Analysis

**Source:** Claude (Opus 4.6)
**Date:** 2026-02-15

---

## Preamble: Where the Gemini Proposal Falls Short

The Gemini proposal is a solid starting point but makes several choices that will cause pain at scale or under real-world conditions:

1. **`unstructured` is a kitchen-sink dependency** — it pulls in dozens of transitive deps, is slow to install, and abstracts away control you'll need when debugging OCR failures on specific document types. Better to compose smaller, focused libraries.

2. **`all-MiniLM-L6-v2` is an outdated embedding choice** — newer models like `nomic-embed-text` (already in the config) or `bge-small-en-v1.5` outperform it on retrieval benchmarks while being the same size.

3. **LlamaIndex adds unnecessary abstraction** — for a system where you control the entire pipeline (ingestion, chunking, retrieval, synthesis), LlamaIndex's opinionated abstractions fight you more than they help. A thin RAG layer over direct Ollama/LiteLLM calls is simpler and more debuggable.

4. **No concurrency model** — the Gemini proposal doesn't address how the watcher, queue worker, API server, and background tasks coordinate. This is the hardest part of the system.

5. **Schema is too thin** — missing tags, processing history, file paths (plural, for dedup), and privacy metadata.

This proposal aims to be implementation-ready.

---

## 1. Python Libraries by Component

### 1.1 Core Runtime & Framework

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `fastapi` | 0.115+ | HTTP API + WebSocket | Async-native, auto OpenAPI docs, best Python API framework |
| `uvicorn` | 0.34+ | ASGI server | Production-grade, works with FastAPI |
| `pydantic` | 2.x | Config & validation | Already a FastAPI dep; use for config parsing too |
| `pydantic-settings` | 2.x | Settings from YAML/env | Replaces manual config loading |
| `typer` | 0.15+ | CLI interface | Same author as FastAPI, consistent patterns |
| `structlog` | 25.x | Structured logging | JSON logs for production, pretty for dev |
| `alembic` | 1.14+ | DB migrations | Essential for schema evolution |

### 1.2 File Watching & Ingestion

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `watchdog` | 6.x | Filesystem events | Industry standard, cross-platform, well-maintained |
| `python-magic` | 0.4+ | MIME type detection | Reliable file type identification beyond extension |
| `xxhash` | 3.x | Fast hashing (pre-filter) | 10x faster than SHA-256 for quick dedup pre-check |
| `hashlib` (stdlib) | — | SHA-256 (canonical hash) | Cryptographic dedup, already in stdlib |

**Design note:** Use xxhash for a fast "have I seen this file size + first-4KB hash?" pre-check, then SHA-256 only for new files. On a 50K document archive, this eliminates 95%+ of unnecessary full-file reads on restart.

### 1.3 Document Processing & OCR

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `pymupdf` (fitz) | 1.25+ | PDF text extraction & rendering | Fastest PDF library in Python; extracts embedded text without OCR; renders pages to images for OCR fallback |
| `paddleocr` | 2.9+ | Local OCR (primary) | Superior to Tesseract on varied layouts, tables, multilingual |
| `pytesseract` | 0.3+ | Local OCR (fallback) | Lightweight fallback; good for clean, typed documents |
| `Pillow` | 11.x | Image preprocessing | Deskew, denoise, contrast enhancement before OCR |
| `pdf2image` | 1.17+ | PDF to image conversion | For scanned PDFs that need OCR |
| `boto3` | 1.x | AWS Textract | Cloud OCR fallback |
| `google-cloud-vision` | 3.x | Google Vision | Cloud OCR fallback (alternative) |

**Critical design choice:** PyMuPDF first tries to extract embedded text from PDFs (instant, zero-cost). Only if the page yields < 50 characters does it fall back to OCR. This skips OCR entirely for ~60% of typical document archives (born-digital PDFs).

### 1.4 Text Processing & Chunking

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `tiktoken` | 0.9+ | Token counting | Accurate token counts for chunk sizing |
| `langdetect` | 1.0+ | Language detection | Route to correct OCR language model |
| `ftfy` | 6.x | Text cleanup | Fixes encoding issues, mojibake from OCR |
| `dateparser` | 1.2+ | Date extraction | Extract document dates from content |

**Chunking strategy:** No library — implement a custom recursive splitter (~100 LOC) that:
1. Splits on `\n\n` (paragraphs) first
2. Falls back to `\n` (lines)
3. Falls back to sentence boundaries (regex)
4. Respects a max token count (512 tokens) with 64-token overlap
5. Preserves metadata (page number, section header if detectable)

This is simpler and more controllable than any chunking library.

### 1.5 Embeddings & Vector Store

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `chromadb` | 0.6+ | Vector storage | Embedded mode, persistent, good Python API |
| `httpx` | 0.28+ | HTTP client for Ollama | Async, connection pooling, timeout control |

**Embedding model:** `nomic-embed-text` via Ollama (768-dim, 8192 token context). No sentence-transformers dependency — call Ollama's `/api/embeddings` endpoint directly. This:
- Eliminates a heavy PyTorch dependency from the main process
- Uses the same Ollama instance as the LLM (one process to manage)
- Allows swapping models without code changes

### 1.6 LLM & Agentic Layer

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `litellm` | 1.x | Unified LLM API | Single interface for Ollama, OpenAI, Anthropic; handles retries, fallbacks |
| `jinja2` | 3.x | Prompt templates | Already a FastAPI dep; battle-tested templating |

**Why not LlamaIndex/LangChain:** For Librarian's use cases (single-hop retrieval, classification, summarization), a thin wrapper around LiteLLM with Jinja2 prompt templates is ~200 LOC and infinitely more debuggable. The "agents" in the PRD are really just prompt chains with tool calls — no framework needed.

### 1.7 Database

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `sqlalchemy` | 2.x | ORM + connection management | Type-safe queries, migration support, async support |
| `aiosqlite` | 0.20+ | Async SQLite driver | Non-blocking DB access from async FastAPI |
| `alembic` | 1.14+ | Schema migrations | Manage schema changes across versions |

### 1.8 Task Queue & Background Processing

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `arq` | 0.26+ | Async task queue | Redis-backed, async-native, lightweight |
| `redis` | 5.x | Queue backend + caching | Also used for caching embeddings, rate limiting |

**Alternative (simpler start):** If Redis is too heavy for NAS deployment, use a SQLite-backed queue table with `asyncio` workers. Upgrade to `arq` + Redis when needed.

### 1.9 Testing & Dev

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | 8.x | Test runner |
| `pytest-asyncio` | 0.25+ | Async test support |
| `pytest-cov` | 6.x | Coverage |
| `ruff` | 0.9+ | Linting + formatting |
| `mypy` | 1.x | Type checking |
| `pre-commit` | 4.x | Git hooks |

---

## 2. Data Flow Diagram

### 2.1 Ingestion Flow

```
                       ┌─────────────────────┐
                       │   Watched Folders   │
                       │ /mnt/nas/documents  │
                       │   /mnt/nas/scans    │
                       └──────────┬──────────┘
                                  │
                                  │ inotify / polling
                                  ▼
                       ┌─────────────────────┐
                       │    File Watcher     │
                       │    (watchdog)       │
                       │                     │
                       │    Filters:         │
                       │  - extension check  │
                       │  - ignore patterns  │
                       │  - debounce (2s)    │
                       └──────────┬──────────┘
                                  │
                                  │ file_path, event_type
                                  ▼
                       ┌─────────────────────┐
                       │   Dedup Pre-Check   │
                       │                     │
                       │  1. file_size       │
                       │  2. xxhash(first 4KB)│
                       │  3. Check DB        │
                       └──────────┬──────────┘
                                  │
                           ┌──────┴──────┐
                           │             │
                     Known file     New/changed
                           │             │
                           ▼             ▼
               ┌──────────────┐ ┌──────────────────┐
               │ Link new path│ │   Task Queue     │
               │ to existing  │ │ (arq / SQLite)   │
               │ doc record   │ │                  │
               └──────────────┘ │ Priority levels: │
                                │  HIGH: user upload│
                                │  NORMAL: watcher  │
                                │  LOW: backfill    │
                                └────────┬─────────┘
                                         │
                                         ▼
                      ┌───────────────────────────┐
                      │    Ingestion Worker       │
                      │    (async, N concurrent)  │
                      │                           │
                      │  1. SHA-256 full hash     │
                      │  2. MIME type detection   │
                      │  3. Metadata extraction   │
                      │  4. Language detection    │
                      │  5. Privacy policy check  │
                      └────────────┬──────────────┘
                                   │
                      ┌─────────────┴────────────┐
                      │                          │
                Has embedded text       Scanned/Image
                (born-digital PDF)      (needs OCR)
                      │                          │
                      ▼                          ▼
            ┌────────────────┐      ┌──────────────────┐
            │   PyMuPDF      │      │    OCR Router    │
            │ text extract   │      │                  │
            │ (instant)      │      │ if sensitive:    │
            └───────┬────────┘      │   → PaddleOCR    │
                    │               │ elif low_conf:   │
                    │               │   → Cloud OCR?   │
                    │               │ else:            │
                    │               │   → PaddleOCR    │
                    │               └────────┬─────────┘
                    │                        │
                    └───────────┬────────────┘
                                │
                                │ extracted text + page metadata
                                ▼
                      ┌──────────────────────┐
                      │   Text Pipeline      │
                      │                      │
                      │  1. ftfy cleanup     │
                      │  2. Language detect  │
                      │  3. Chunking (512tok)│
                      │  4. Date extraction  │
                      │  5. Confidence score │
                      └──────────┬───────────┘
                                 │
                      ┌──────────┴───────────┐
                      │                      │
                      ▼                      ▼
            ┌──────────────────┐   ┌──────────────────┐
            │     SQLite       │   │     Ollama       │
            │                  │   │ /api/embeddings  │
            │  - document row  │   │                  │
            │  - chunk rows    │   │ nomic-embed-text │
            │  - file paths    │   └────────┬─────────┘
            │  - processing log│            │
            └──────────────────┘            │ vectors
                                            ▼
                                   ┌──────────────────┐
                                   │    ChromaDB      │
                                   │                  │
                                   │  - chunk vectors │
                                   │  - chunk metadata│
                                   └──────────────────┘
```

### 2.2 Query Flow

```
    User Query
    "Does my insurance
      cover rentals?"
         │
         ▼
┌──────────────┐    ┌──────────────────────────────────────────┐
│   FastAPI    │    │         Query Pipeline                   │
│ POST /query  │───▶│                                          │
└──────────────┘    │  1. Embed query via Ollama               │
                    │  2. ChromaDB similarity search (top-K)    │
                    │  3. Fetch chunk text + doc metadata       │
                    │  4. Re-rank chunks by relevance (optional)│
                    │  5. Build context window                  │
                    │  6. LLM synthesis (LiteLLM → Ollama)      │
                    │  7. Extract source citations              │
                    │  8. Return answer + sources               │
                    └──────────────────────────────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    Response      │
                    │                  │
                    │  answer: "Yes,   │
                    │   your policy..."│
                    │  sources:        │
                    │   - doc: ins.pdf │
                    │     page: 14     │
                    │     chunk: "..." │
                    │  confidence: 0.87│
                    └──────────────────┘
```

### 2.3 Classification Flow

```
 New Document Ingested
         │
         ▼
┌──────────────────────────────────────────┐
│         Classification Agent             │
│                                          │
│  Input: first 2 chunks of document text  │
│                                          │
│  1. LLM prompt: "Classify this document. │
│     Return: category, tags[], date,      │
│     summary (1 sentence)"                │
│                                          │
│  2. Parse structured JSON response       │
│  3. Write tags + category to SQLite      │
│  4. Optionally suggest filing location   │
│                                          │
│  Cost: 1 LLM call per document           │
└──────────────────────────────────────────┘
```

---

## 3. Database Schema (SQLite)

### 3.1 Entity-Relationship Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  documents  │──1:N──│  file_paths  │     │ document_chunks │
│             │     └──────────────┘     │                 │
│  id (PK)    │                         │  id (PK)        │
│content_hash │──1:N────────────────────▶│  document_id(FK)│
│    ...      │                         │  vector_id      │
└──────┬──────┘                         │  chunk_text     │
       │                                │  page_number    │
       │  M:N                           └─────────────────┘
       │
┌──────┴──────┐
│    tags     │
│             │
│  id (PK)    │
│    name     │
└─────────────┘
```

### 3.2 Full Schema (SQL)

```sql
-- Core document identity (content-addressed)
CREATE TABLE documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT NOT NULL UNIQUE,            -- SHA-256 of file content
    title           TEXT,                            -- Extracted or inferred title
    document_type   TEXT NOT NULL,                   -- MIME type (application/pdf, image/png, etc.)
    page_count      INTEGER,
    language        TEXT DEFAULT 'en',               -- ISO 639-1 detected language
    ocr_engine      TEXT,                            -- 'pymupdf_native', 'paddleocr', 'tesseract', 'textract', 'google_vision'
    ocr_confidence  REAL,                            -- 0.0 - 1.0 average confidence
    processing_mode TEXT NOT NULL DEFAULT 'local',   -- 'local' or 'cloud'
    category        TEXT,                            -- LLM-assigned category
    summary         TEXT,                            -- LLM-generated 1-sentence summary
    extracted_date  TEXT,                            -- Date found within document content (ISO 8601)
    status          TEXT NOT NULL DEFAULT 'pending', -- 'pending','processing','completed','error','reprocessing'
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    file_size_bytes INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    processed_at    TEXT
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);
CREATE INDEX idx_documents_category ON documents(category);

-- Multiple file paths can point to same content (deduplication)
CREATE TABLE file_paths (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_path    TEXT NOT NULL UNIQUE,               -- Absolute path
    is_primary   INTEGER NOT NULL DEFAULT 1,          -- 1 = canonical path, 0 = duplicate
    first_seen   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_seen    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at   TEXT                                 -- Soft-delete when file disappears
);

CREATE INDEX idx_file_paths_document_id ON file_paths(document_id);
CREATE INDEX idx_file_paths_file_path ON file_paths(file_path);

-- Document chunks with text (source of truth for retrieval)
CREATE TABLE document_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    vector_id    TEXT NOT NULL UNIQUE,               -- UUID, maps to ChromaDB entry
    chunk_index  INTEGER NOT NULL,                   -- Order within document
    chunk_text   TEXT NOT NULL,
    page_number  INTEGER,                            -- Source page (if applicable)
    token_count  INTEGER NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector_id ON document_chunks(vector_id);

-- Tags (many-to-many)
CREATE TABLE tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    source      TEXT NOT NULL DEFAULT 'auto',         -- 'auto' (LLM) or 'manual' (user)
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (document_id, tag_id)
);

-- Processing history (audit trail)
CREATE TABLE processing_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    action       TEXT NOT NULL,                       -- 'ingested','ocr_local','ocr_cloud','classified','reprocessed','error'
    details      TEXT,                                -- JSON blob with action-specific data
    duration_ms  INTEGER,                             -- How long this step took
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_processing_log_document_id ON processing_log(document_id);

-- Full-text search on chunk content
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_text,
    content='document_chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER chunks_fts_insert AFTER INSERT ON document_chunks BEGIN
    INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
END;

CREATE TRIGGER chunks_fts_delete AFTER DELETE ON document_chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.id, old.chunk_text);
END;

CREATE TRIGGER chunks_fts_update AFTER UPDATE OF chunk_text ON document_chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.id, old.chunk_text);
    INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.id, new.chunk_text);
END;

-- Filing suggestions (proactive organization)
CREATE TABLE filing_suggestions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    current_path   TEXT NOT NULL,
    suggested_path TEXT NOT NULL,
    reason         TEXT,                              -- LLM-generated explanation
    status         TEXT NOT NULL DEFAULT 'pending',   -- 'pending','accepted','rejected','expired'
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    resolved_at    TEXT
);
```

### 3.3 ChromaDB Collection Schema

```python
# Single collection with rich metadata for filtering
collection = chroma_client.get_or_create_collection(
    name="librarian_chunks",
    metadata={"hnsw:space": "cosine"},  # cosine similarity
)

# Each entry:
collection.add(
    ids=["chunk-uuid-here"],
    embeddings=[[0.1, 0.2, ...]],         # 768-dim from nomic-embed-text
    documents=["The policy covers..."],    # chunk text (for Chroma's built-in search)
    metadatas=[{
        "document_id": 42,
        "content_hash": "abc123...",
        "page_number": 14,
        "chunk_index": 3,
        "category": "insurance",
        "language": "en",
        "tags": "insurance,legal,auto",    # Comma-separated (Chroma metadata is flat)
    }],
)
```

---

## 4. API Surface

### 4.1 REST API (FastAPI)

#### Documents

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/documents` | List documents (paginated, filterable) | Optional |
| `GET` | `/api/v1/documents/{id}` | Get document details + chunks | Optional |
| `POST` | `/api/v1/documents/upload` | Manual file upload | Optional |
| `DELETE` | `/api/v1/documents/{id}` | Remove document from index (not disk) | Optional |
| `PATCH` | `/api/v1/documents/{id}` | Update tags, category, title | Optional |
| `POST` | `/api/v1/documents/{id}/reprocess` | Re-run OCR/embedding pipeline | Optional |

#### Search & Query

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/search` | Semantic vector search (returns chunks) |
| `POST` | `/api/v1/query` | RAG query (returns LLM-synthesized answer) |
| `GET` | `/api/v1/search/fulltext?q=` | FTS5 keyword search |

#### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/status` | System health, queue depth, storage stats |
| `GET` | `/api/v1/queue` | Current processing queue |
| `POST` | `/api/v1/queue/pause` | Pause ingestion |
| `POST` | `/api/v1/queue/resume` | Resume ingestion |
| `GET` | `/api/v1/tags` | List all tags with document counts |
| `GET` | `/api/v1/config` | Current configuration (redacted secrets) |

#### Filing Suggestions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/suggestions` | List pending filing suggestions |
| `POST` | `/api/v1/suggestions/{id}/accept` | Accept and execute a filing move |
| `POST` | `/api/v1/suggestions/{id}/reject` | Dismiss a suggestion |

### 4.2 WebSocket API

```
WS /api/v1/ws/events
```

Real-time event stream for UI updates:

```json
{"event": "document.discovered", "data": {"path": "/mnt/nas/new.pdf"}}
{"event": "document.processing", "data": {"id": 42, "step": "ocr", "progress": 0.6}}
{"event": "document.completed", "data": {"id": 42, "title": "Insurance Policy"}}
{"event": "document.error", "data": {"id": 42, "error": "OCR timeout"}}
{"event": "suggestion.created", "data": {"id": 7, "from": "...", "to": "..."}}
{"event": "queue.stats", "data": {"pending": 12, "processing": 3, "completed": 1847}}
```

### 4.3 Key Request/Response Schemas

```python
# POST /api/v1/query
class QueryRequest(BaseModel):
    query: str                           # Natural language question
    top_k: int = 10                      # Number of chunks to retrieve
    filter_tags: list[str] | None = None # Optional tag filter
    filter_category: str | None = None   # Optional category filter
    include_sources: bool = True         # Include source chunks in response

class QueryResponse(BaseModel):
    answer: str                          # LLM-synthesized answer
    confidence: float                    # 0.0-1.0 retrieval relevance score
    sources: list[Source]                # Supporting evidence
    query_time_ms: int                   # Total query latency

class Source(BaseModel):
    document_id: int
    title: str | None
    file_path: str
    page_number: int | None
    chunk_text: str                      # Relevant excerpt
    similarity: float                    # Vector similarity score

# POST /api/v1/search
class SearchRequest(BaseModel):
    query: str
    top_k: int = 20
    filter_tags: list[str] | None = None
    filter_category: str | None = None
    threshold: float = 0.3               # Minimum similarity

class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    search_time_ms: int

class SearchResult(BaseModel):
    document_id: int
    title: str | None
    file_path: str
    page_number: int | None
    chunk_text: str
    similarity: float
    tags: list[str]
    category: str | None

# GET /api/v1/documents
class DocumentListParams(BaseModel):
    page: int = 1
    per_page: int = 50
    status: str | None = None
    category: str | None = None
    tag: str | None = None
    sort_by: str = "created_at"          # created_at, title, file_size_bytes
    sort_order: str = "desc"             # asc, desc
    q: str | None = None                 # Full-text search filter
```

---

## 5. Key Architectural Decisions

### 5.1 Process Model: Single Process, Multiple Async Workers

**Decision:** Run everything in one Python process using `asyncio`.

**Rationale:**
- NAS hardware has limited RAM — separate processes waste memory
- `asyncio` can handle file watching, queue processing, and API serving concurrently
- Simpler deployment (one container, one process)
- Use `asyncio.Semaphore` to limit concurrent OCR jobs (CPU-bound)

**Structure:**
```
Main Process (uvicorn)
 ├── FastAPI routes (async)
 ├── WebSocket manager (async)
 ├── File watcher thread (watchdog → asyncio queue)
 ├── Worker pool (N async workers consuming from queue)
 └── Background scheduler (periodic tasks: cleanup, re-check missing files)
```

**Escape hatch:** If OCR CPU-blocking is a problem, offload to `ProcessPoolExecutor` for the OCR step only (PaddleOCR releases the GIL poorly). This keeps the async event loop responsive.

### 5.2 Content-Addressed Storage

**Decision:** Documents are identified by content hash, not file path.

**Rationale:**
- A document may exist at multiple paths (copies, moves, renames)
- Hash-based identity means "move" ≠ "reprocess"
- The `file_paths` table maps N paths → 1 document
- On file delete: soft-delete the path, keep the document if other paths exist

### 5.3 Two-Phase Hashing

**Decision:** xxhash pre-filter → SHA-256 canonical hash.

**Rationale:**
- On startup/backfill, the watcher must scan all files to detect changes
- SHA-256 on 50K files (avg 2MB each = 100GB) takes ~15 minutes
- xxhash on first 4KB + file size takes ~2 seconds for 50K files
- Only compute SHA-256 for files that pass the pre-filter as potentially new

### 5.4 PyMuPDF Before OCR

**Decision:** Always attempt native PDF text extraction before OCR.

**Rationale:**
- ~60% of PDFs are "born-digital" (contain embedded text layer)
- Native extraction is instant vs. 5-30 seconds for OCR per page
- For a 50K archive, this saves hundreds of hours of compute
- If extracted text < 50 chars per page → assume scanned, fall back to OCR

### 5.5 Ollama for Everything Local

**Decision:** Use Ollama for embeddings AND LLM inference.

**Rationale:**
- Single dependency to manage for all local AI
- User already needs Ollama for the LLM — reuse for embeddings
- `nomic-embed-text` via Ollama matches or exceeds `sentence-transformers` quality
- Eliminates PyTorch from the main application's dependency tree (huge install size reduction)

### 5.6 LiteLLM as the LLM Router

**Decision:** All LLM calls go through LiteLLM.

**Rationale:**
- Uniform API whether calling Ollama, OpenAI, or Anthropic
- Built-in retry logic and fallback chains
- Provider can be changed in config without code changes
- Supports streaming for real-time UI updates

### 5.7 Hybrid Search (Vector + FTS5)

**Decision:** Support both semantic search (ChromaDB) and keyword search (FTS5), with optional fusion.

**Rationale:**
- Semantic search fails on exact terms (policy numbers, names, specific codes)
- FTS5 fails on conceptual queries ("documents about retirement planning")
- Reciprocal Rank Fusion (RRF) of both results gives best of both worlds
- FTS5 is free (built into SQLite) — zero additional cost

### 5.8 Event-Driven UI Updates via WebSocket

**Decision:** Push real-time events to connected clients over WebSocket.

**Rationale:**
- Processing can take minutes — polling wastes resources
- Users want to see their document being processed in real-time
- WebSocket is well-supported by FastAPI and all modern browsers
- Also enables future features like live collaboration

---

## 6. Bottlenecks & Mitigation

### 6.1 OCR is CPU-Bound and Slow

**Impact:** PaddleOCR processes ~2-5 pages/second on a modern CPU. A 50K document archive with avg. 5 pages = 250K pages = 14-35 hours.

**Mitigations:**
1. **PyMuPDF native extraction first** — eliminates OCR for ~60% of PDFs
2. **ProcessPoolExecutor** — run OCR in separate process to not block async loop
3. **Priority queue** — newest files first, backfill in background
4. **GPU acceleration** — PaddleOCR supports CUDA; if user has GPU, processing is 10-20x faster
5. **Progress persistence** — if interrupted, resume from last unprocessed document (not from scratch)
6. **Incremental backfill** — process 100 docs, sleep 30s, repeat (prevents thermal throttling on NAS)

### 6.2 Embedding Generation Throughput

**Impact:** Ollama embedding calls are sequential HTTP requests. Each chunk takes ~50-100ms. 50K docs × 10 chunks avg = 500K chunks = 7-14 hours.

**Mitigations:**
1. **Batch embedding requests** — Ollama supports batch mode; send 32 chunks per request
2. **Pipeline parallelism** — embed while next document is being OCR'd
3. **Cache embeddings** — store in ChromaDB; never re-embed unchanged chunks
4. **Optional: sentence-transformers fallback** — for initial backfill, run embeddings locally in-process (faster than HTTP roundtrips to Ollama)

### 6.3 LLM RAM Consumption

**Impact:** A 7B parameter model (Q4) uses ~4GB RAM. Combined with PaddleOCR (~1GB), ChromaDB (~500MB), and Python overhead (~500MB), total is ~6-7GB. Tight on 16GB NAS with OS overhead.

**Mitigations:**
1. **Lazy LLM loading** — only load the LLM when a query/classification arrives; unload after 5-min idle timeout
2. **Smaller models for classification** — use `llama3.2:1b` (~1GB) for auto-tagging; reserve 3B+ for queries
3. **Separate Ollama host** — config option to point at a more powerful machine on the network
4. **Queue classification** — don't classify at ingestion time; batch-classify during idle periods

### 6.4 SQLite Write Contention

**Impact:** SQLite allows only one writer at a time. Under heavy ingestion (multiple workers), this becomes a bottleneck.

**Mitigations:**
1. **WAL mode** — `PRAGMA journal_mode=WAL` allows concurrent reads during writes
2. **Batch inserts** — buffer writes and flush every 100 records or 5 seconds
3. **Connection pooling** — SQLAlchemy manages connections; avoid "database is locked" errors
4. **Separate read/write connections** — read queries use a separate connection from the write path

### 6.5 Large File Handling

**Impact:** Some PDFs can be 500MB+ (scanned books). These can OOM during processing.

**Mitigations:**
1. **Streaming processing** — process page-by-page, never load entire PDF into memory
2. **File size limits** — configurable max (default 100MB), skip with warning
3. **Temporary extraction** — render PDF pages to temp images, process, delete
4. **Memory monitoring** — check available RAM before processing large files; defer if low

### 6.6 ChromaDB at Scale

**Impact:** ChromaDB embedded mode with 500K+ vectors (50K docs × 10 chunks) may slow down. HNSW index rebuilds on restart can take minutes.

**Mitigations:**
1. **Metadata filtering** — use Chroma's `where` clause to narrow search space before vector comparison
2. **Collection sharding** — split by year or category if a single collection gets too large (future)
3. **pgvector upgrade path** — the architecture supports swapping to pgvector for larger deployments
4. **Persist directory on SSD** — avoid NAS HDDs for the vector store; use local SSD if available

---

## 7. Project Structure

```
librarian/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── config/
│   └── config.example.yaml
├── src/
│   └── librarian/
│       ├── __init__.py
│       ├── __main__.py              # Entry point (typer CLI)
│       ├── config.py                # Pydantic settings model
│       ├── app.py                   # FastAPI app factory
│       ├── api/
│       │   ├── __init__.py
│       │   ├── documents.py         # Document CRUD routes
│       │   ├── search.py            # Search & query routes
│       │   ├── system.py            # Health, queue, config routes
│       │   ├── suggestions.py       # Filing suggestion routes
│       │   └── websocket.py         # WebSocket event stream
│       ├── core/
│       │   ├── __init__.py
│       │   ├── watcher.py           # Filesystem watcher
│       │   ├── queue.py             # Task queue (arq or SQLite)
│       │   ├── worker.py            # Ingestion worker pool
│       │   └── scheduler.py         # Background periodic tasks
│       ├── processing/
│       │   ├── __init__.py
│       │   ├── hasher.py            # xxhash + SHA-256
│       │   ├── extractor.py         # PyMuPDF text extraction
│       │   ├── ocr.py               # OCR router (Paddle/Tesseract/Cloud)
│       │   ├── chunker.py           # Text chunking
│       │   ├── embedder.py          # Embedding via Ollama
│       │   └── classifier.py        # LLM-based classification
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py          # SQLAlchemy models + session
│       │   ├── models.py            # ORM models
│       │   ├── vector_store.py      # ChromaDB wrapper
│       │   └── repositories.py      # Data access layer
│       └── llm/
│           ├── __init__.py
│           ├── client.py            # LiteLLM wrapper
│           ├── prompts/             # Jinja2 prompt templates
│           │   ├── classify.j2
│           │   ├── query.j2
│           │   ├── summarize.j2
│           │   └── file_suggest.j2
│           └── agents.py            # Query, classify, organize agents
├── tests/
│   ├── conftest.py
│   ├── test_watcher.py
│   ├── test_processing.py
│   ├── test_search.py
│   └── fixtures/
│       ├── sample.pdf
│       └── sample_scan.png
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/
    ├── PRD.md
    └── ...
```

---

## 8. Features MISSING from the PRD

The following capabilities are absent from the PRD but would be valuable for a production-ready document intelligence platform:

### 8.1 Critical Gaps (Should Be in v1)

**1. Document Versioning / Change Detection**
The PRD handles deduplication (same file, different path) but not *updated* documents. What happens when the user edits `contract_v2.pdf` and saves it to the same path? The system needs:
- Detection that an existing path now has a different hash
- Re-processing the new version
- Optionally keeping the old version's metadata for comparison
- A `versions` table or version counter on documents

**2. Error Recovery & Retry Strategy**
The PRD mentions processing status but has no error handling specification:
- What happens when OCR fails? (retry? skip? alert?)
- What if Ollama is unreachable? (queue backlog? degrade gracefully?)
- Max retry count? Exponential backoff?
- Dead letter queue for permanently failed documents?

**3. Backup & Restore**
For a system storing irreplaceable index data:
- How to back up SQLite + ChromaDB atomically?
- Export/import functionality
- Disaster recovery procedure
- What if the ChromaDB gets corrupted? Can we rebuild from SQLite chunk text?

**4. File Deletion Handling**
The PRD covers file creation and deduplication but not deletion:
- What happens when a watched file is deleted from disk?
- Soft-delete from index? Immediate purge? User confirmation?
- Orphan detection (indexed files that no longer exist on disk)

**5. Monitoring & Observability**
No mention of how operators know the system is healthy:
- Health check endpoint
- Metrics (documents processed/hour, queue depth, error rate)
- Alerting when queue is stuck or disk is full
- Processing time histograms

### 8.2 Important Gaps (Should Be in v2)

**6. Multi-Language OCR Support**
The PRD only mentions English. Real-world archives often contain:
- Documents in multiple languages
- Mixed-language documents (e.g., legal docs with Latin terms)
- Non-Latin scripts (Cyrillic, CJK, Arabic)
- Language auto-detection should route to appropriate OCR model

**7. Table & Structured Data Extraction**
The "utility bill kWh" user story (3.2) implies structured data extraction, but the PRD has no specification for:
- Table detection and parsing
- Key-value pair extraction (invoice number, total, dates)
- Structured metadata storage for extracted fields
- This is a fundamentally different problem from free-text OCR

**8. Access Control & Multi-User**
The PRD assumes single-user, but the monetization doc mentions multi-user tiers:
- Authentication (even basic API key)
- Per-user document visibility
- Shared vs. private tags
- Role-based access (admin vs. viewer)

**9. Document Preview & Annotation**
Users will want to:
- View a thumbnail/preview of documents in the UI
- See OCR text overlaid on the original scan (to verify accuracy)
- Highlight and correct OCR errors manually
- Mark sections as "ignore" or "important"

**10. Incremental Re-Indexing**
What happens when:
- The embedding model is changed? (all vectors must be regenerated)
- The chunking strategy is updated? (all chunks must be re-split)
- The OCR engine is upgraded? (should documents be re-OCR'd?)
- Need a "reindex" command that can selectively re-process

### 8.3 Nice-to-Have Gaps (v3+)

**11. Document Relationships & Cross-References**
- "This invoice references PO #12345" → link to the PO document
- "This amendment modifies contract ABC" → link to the contract
- Automatic relationship detection via entity extraction

**12. Calendar Integration**
- Extract dates from documents (due dates, renewal dates, expiration)
- Push reminders: "Your insurance policy expires in 30 days"
- Timeline view of all document-related dates

**13. Email Ingestion**
- Watch an IMAP mailbox for attachments
- Save and index email attachments automatically
- Preserve email metadata (from, subject, date) as document context

**14. Mobile Access & Capture**
- Responsive web UI for phone access
- Camera capture → direct upload → OCR pipeline
- Share-to-Librarian from mobile OS

**15. Export & Integration**
- Export search results as CSV/PDF
- Webhook notifications on document events
- Integration with common tools (Notion, Obsidian, Home Assistant)
- IFTTT/Zapier triggers

**16. OCR Confidence Feedback Loop**
- Show users low-confidence OCR results for manual correction
- Use corrections to fine-tune or select better OCR parameters
- Track accuracy metrics over time

**17. Retention Policies**
- Auto-delete documents after N years (configurable per category)
- GDPR "right to be forgotten" — purge all traces of specific documents
- Archival tiers (move old documents to cold storage)

**18. Bandwidth & Storage Quotas**
- For hosted/multi-user deployments
- Per-user storage limits
- Rate limiting on API and cloud OCR calls
- Cost tracking for cloud API usage

---

## 9. Implementation Priority (Recommended Milestone Adjustments)

The PRD milestones are reasonable but should be reordered for faster time-to-value:

| Phase | Deliverable | Change from PRD |
|-------|-------------|-----------------|
| **M1** | Project skeleton + config + CLI + SQLite schema + Alembic | Added config system and DB migrations |
| **M2** | File watcher + dedup + ingestion queue | Same, but queue before OCR |
| **M3** | PyMuPDF text extraction (born-digital PDFs) | **New** — get searchable results before touching OCR |
| **M4** | FTS5 keyword search + basic API | **Moved up** — users can search before vectors exist |
| **M5** | PaddleOCR for scanned documents | Was M3 |
| **M6** | Ollama embeddings + ChromaDB + semantic search | Was M4 |
| **M7** | RAG query interface (LiteLLM) | Same |
| **M8** | Auto-tagging + classification | Same |
| **M9** | Cloud OCR fallback + privacy controls | Same |
| **M10** | WebSocket events + real-time UI | **New** |
| **M11** | Docker compose + deployment | Same |

**Key insight:** By moving PyMuPDF text extraction and FTS5 search before OCR/vectors, users get a working searchable archive in M4 — without any AI dependencies. This makes the product useful much sooner and reduces the "time to wow."
