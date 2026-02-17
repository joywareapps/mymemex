# Architecture Decisions

## ADR-001: Hybrid Memory Architecture

**Status:** Proposed
**Date:** 2026-02-15

### Context

We need a document intelligence system that can:
1. Process documents locally for privacy
2. Optionally use cloud services for better accuracy
3. Scale to 50,000+ documents
4. Run on consumer hardware (NAS or small server)

### Decision

Implement a **Hybrid Memory** architecture with distinct layers:
- **Ingestion Layer** — File watching, hashing, queueing
- **Intelligence Layer** — OCR and embeddings (local or cloud)
- **Storage Layer** — SQLite for metadata, ChromaDB for vectors
- **Agentic Layer** — Query, classification, organization

### Consequences

- ✅ Clear separation of concerns
- ✅ Each layer can be swapped/improved independently
- ✅ Privacy-sensitive operations isolated
- ⚠️ More complex than monolithic design
- ⚠️ Requires careful state management between layers

---

## ADR-002: SQLite for Metadata Storage

**Status:** Proposed
**Date:** 2026-02-15

### Context

We need a database to store:
- File metadata (path, hash, size, timestamps)
- Document relationships
- Processing status
- Tags and categories

### Decision

Use **SQLite** as the primary metadata store.

### Rationale

- Zero configuration, embedded database
- ACID compliant
- Full-text search via FTS5 extension
- Portable single-file database
- Sufficient for 50,000 documents
- Easy backup (copy single file)

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| PostgreSQL | More scalable, pgvector built-in | Requires server, overkill for personal use |
| DuckDB | Fast analytics | Less mature, larger footprint |

---

## ADR-003: ChromaDB for Vector Storage

**Status:** Proposed
**Date:** 2026-02-15

### Context

We need to store document embeddings for semantic search.

### Decision

Use **ChromaDB** as the default vector store with **pgvector** as an optional alternative.

### Rationale

- Embedded mode (no server required)
- Built-in embedding functions
- Simple Python API
- Persistent storage
- Easy local development

### When to use pgvector instead

- Running PostgreSQL already
- Need advanced vector operations
- Multi-user deployment

---

## ADR-004: Python as Primary Language

**Status:** Proposed
**Date:** 2026-02-15

### Context

We need a language for the core implementation.

### Decision

Use **Python 3.11+** as the primary language.

### Rationale

- Rich ecosystem for ML/OCR (Tesseract, PaddleOCR, Transformers)
- Native ChromaDB/SQLite support
- Good async support for file watching
- Easy prototyping
- Wide deployment options

### Future Consideration

Rust could be used for performance-critical components (hashing, file watching) if needed.

---

## ADR-005: Local-First Privacy Model

**Status:** Proposed
**Date:** 2026-02-15

### Context

Users may have sensitive documents (financial, medical) that should never leave their network.

### Decision

Implement **Local-First** processing as the default:
1. All processing defaults to local models
2. Cloud APIs require explicit opt-in per file/folder
3. Sensitive paths auto-force local processing
4. Cloud results are not persisted longer than necessary

### Implementation

```yaml
privacy:
  default_mode: local
  sensitive_paths:
    - /mnt/nas/financial
    - /mnt/nas/medical
  cloud_fallback_threshold: 70  # Only suggest cloud if confidence < 70%
```

---

## ADR-006: SHA-256 for Deduplication

**Status:** Proposed
**Date:** 2026-02-15

### Context

We need to identify duplicate files across folders.

### Decision

Use **SHA-256** hashes for file identification.

### Rationale

- Cryptographically collision-resistant
- Fast computation
- Standard across tools
- 256-bit (64 hex chars) is manageable

### Implementation

```python
import hashlib

def compute_file_hash(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

---

## ADR-007: MCP-First Interface

**Status:** Accepted
**Date:** 2026-02-17

### Context

We need to provide conversational access to the document library. Options:
1. Build a custom chat UI with RAG pipeline
2. Expose capabilities via Model Context Protocol (MCP)

### Decision

Implement **MCP-first** approach as the primary conversational interface.

### Rationale

1. **Immediate utility** — Works with existing clients (Claude Desktop, OpenClaw)
2. **Reduced development** — No custom chat UI needed for MVP
3. **Flexible integration** — Any MCP-compatible client can connect
4. **User context support** — MCP can pass user identity for multi-user scenarios
5. **Progressive enhancement** — Custom chat UI can be added later (M12)

### Prerequisites

**M6.5 (Service Layer Extraction)** must be completed before M7 implementation. MCP tools are thin wrappers that call the service layer — without it, business logic would need to be duplicated between REST API handlers and MCP tool handlers.

### Implementation

```python
# MCP server integrated into main process
# Uses service layer (src/librarian/services/) — no duplicate logic
# Two transport modes:
# - stdio: Local integration (Claude Desktop)
# - HTTP/SSE: Remote access (OpenClaw, web apps)
```

### Tools Exposed

1. `search_documents` — Keyword/semantic/hybrid search
2. `get_document` — Retrieve document metadata + content
3. `get_document_text` — Page-range text retrieval for LLM context
4. `list_documents` — Paginated listing with filters
5. `add_tag` / `remove_tag` — Tag management
6. `upload_document` — Add new documents (file_path primary, base64 fallback with size limits)
7. `get_library_stats` — Library statistics
8. `watch_directory` — Add new watch paths (with path boundary validation)

### Security Considerations

- `watch_directory` validates paths against `allowed_parent_paths`
- `upload_document` enforces size limits and path validation
- HTTP/SSE transport defaults to localhost binding with rate limiting
- Network exposure requires reverse proxy with TLS

### Consequences

- ✅ Conversational access available immediately (M7)
- ✅ No custom chat UI needed for MVP
- ✅ Works with user's existing AI assistants
- ✅ Multi-user context supported via MCP
- ✅ Security boundaries enforced on filesystem operations
- ⚠️ Requires MCP client setup (Claude Desktop config)
- ⚠️ Requires M6.5 service layer extraction first
- ⚠️ Custom chat UI deferred to M12

### Integration with Existing Architecture

```
FastAPI (REST) ← Shared Service Layer → MCP Server
       ↓                    ↓                  ↓
  Web Browser          CLI Tools        MCP Clients
```

All three interfaces (REST, CLI, MCP) use the same service layer, ensuring consistency and reducing maintenance burden.

---

## ADR-008: Service Layer Design

**Status:** Accepted
**Date:** 2026-02-17

### Context

The current codebase (M1-M6) has business logic scattered across:
- **API route handlers** (`src/librarian/routers/`) — validation, database queries, response formatting mixed together
- **Pipeline stages** (`src/librarian/pipeline/`) — ingestion logic tightly coupled to the pipeline runner
- **Repositories** (`src/librarian/repositories/`) — some business logic leaked into data-access code

M7 (MCP Server) will need to call the same business logic as the REST API. Without a service layer, we would either:
1. Duplicate logic between REST handlers and MCP tool handlers (maintenance nightmare)
2. Have MCP tools call REST endpoints internally (unnecessary overhead and coupling)

### Decision

Extract a **service layer** (`src/librarian/services/`) as an explicit architectural boundary between interface handlers (REST, MCP, CLI) and data access (repositories, ChromaDB client).

### Architecture

```
┌──────────────────────────────────────────────────┐
│                 Interface Layer                    │
│   REST API    │    MCP Tools    │    CLI Commands  │
│  (FastAPI)    │  (mcp SDK)      │    (Typer)       │
├──────────────────────────────────────────────────┤
│                 Service Layer                      │
│  DocumentService │ SearchService │ TagService      │
│  IngestService   │ StatsService  │                 │
├──────────────────────────────────────────────────┤
│                 Data Access Layer                   │
│  Repositories (SQLAlchemy) │ ChromaDB Client       │
├──────────────────────────────────────────────────┤
│                 Storage Layer                      │
│       SQLite          │       ChromaDB             │
└──────────────────────────────────────────────────┘
```

### Service Responsibilities

| Service | Responsibility |
|---------|---------------|
| `DocumentService` | Document CRUD, status transitions, file operations |
| `SearchService` | Keyword, semantic, hybrid search orchestration |
| `TagService` | Tag CRUD, bulk operations, auto-tag integration |
| `IngestService` | Upload handling, pipeline triggering, inbox management |
| `StatsService` | Library statistics aggregation |

### Design Principles

1. **Services own business logic** — Validation rules, status transitions, search orchestration
2. **Services own transactions** — Each service method is a unit of work
3. **Repositories own queries** — SQL/ChromaDB queries stay in repositories
4. **Interface handlers are thin** — Validate input, call service, format output
5. **Services are independently testable** — Constructor injection for dependencies

### Example

```python
# Before (M6): business logic in API handler
@router.get("/api/v1/search/hybrid")
async def search_hybrid(q: str, limit: int = 10, db: Session = Depends(get_db)):
    # Business logic mixed with handler
    keyword_results = db.execute(fts5_query(q))
    vector_results = chroma_client.query(embed(q))
    merged = rrf_merge(keyword_results, vector_results)
    return {"results": merged[:limit]}

# After (M6.5): thin handler calling service
@router.get("/api/v1/search/hybrid")
async def search_hybrid(q: str, limit: int = 10, search: SearchService = Depends()):
    results = await search.hybrid(query=q, limit=limit)
    return {"results": results}

# MCP tool calls the same service
@mcp.tool()
async def search_documents(query: str, mode: str = "hybrid", limit: int = 10):
    search = SearchService()
    results = await search.search(query=query, mode=mode, limit=limit)
    return results
```

### Consequences

- ✅ MCP tools and REST handlers share identical business logic
- ✅ Services are independently testable
- ✅ Clear architectural boundaries
- ✅ Easier to add new interfaces (CLI, WebSocket, etc.)
- ✅ Incremental extraction — can be done service by service
- ⚠️ 2-3 days of refactoring before M7 can start
- ⚠️ Existing tests may need minor updates to test services directly

### Migration Strategy

1. Create `src/librarian/services/__init__.py`
2. Extract `SearchService` first (most complex, most value)
3. Extract `DocumentService` and `TagService`
4. Extract `IngestService` and `StatsService`
5. Refactor API handlers to call services
6. Run full test suite after each extraction

---

## ADR-009: MCP Security Model

**Status:** Accepted
**Date:** 2026-02-17

### Context

MCP tools like `watch_directory` and `upload_document` accept file paths, which creates a security surface:
- `watch_directory` could be used to add arbitrary system directories (e.g., `/etc`, `~/.ssh`)
- `upload_document` with `file_path` could reference sensitive files
- HTTP/SSE transport exposes the server to network requests

### Decision

Implement **defense-in-depth** security for MCP operations:

1. **Path boundaries** — All file path operations validated against `allowed_parent_paths`
2. **Localhost by default** — HTTP transport binds to 127.0.0.1
3. **Rate limiting** — Configurable per-minute request limit for HTTP transport
4. **TLS warnings** — Log warnings when binding to network interfaces without TLS
5. **Upload size limits** — Base64 uploads capped at configurable maximum (default 5MB)

### Rationale

- Librarian manages sensitive personal documents — security must be baked in, not bolted on
- Path boundary validation prevents the most dangerous attack vector (filesystem access)
- Localhost binding eliminates network attack surface by default
- Rate limiting prevents abuse of the HTTP transport
- TLS is not enforced (users may have valid reasons) but strongly warned about

### Implementation

```yaml
mcp:
  http:
    host: 127.0.0.1  # localhost only
    rate_limit_requests_per_minute: 60
    require_tls_for_network: true  # warn on 0.0.0.0 without TLS
  security:
    allowed_parent_paths:
      - /home/user/documents
    max_upload_size_mb: 5
```

### Consequences

- ✅ Filesystem access is bounded and predictable
- ✅ Network exposure is opt-in
- ✅ Simple configuration — sane defaults for personal use
- ⚠️ Users who want broader filesystem access must explicitly configure it
- ⚠️ TLS is a warning, not enforcement — users can ignore it
