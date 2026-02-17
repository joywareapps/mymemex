# M6.5: Service Layer Extraction

**Goal:** Extract business logic from API handlers and pipeline code into a clean service layer, establishing the shared backend that MCP tools and REST endpoints will both call.

**Context:**
- Librarian M1-M6 is complete and working
- Business logic is scattered across API route handlers, pipeline stages, and repositories
- M7 (MCP Server) requires a service layer to avoid duplicating logic
- Current test coverage: 83 tests (68 passing, 15 skip)

---

## Current Architecture Problems

**Business logic locations (scattered):**

1. **API handlers** (`src/librarian/routers/`) — validation, DB queries, response formatting mixed together
2. **Pipeline stages** (`src/librarian/pipeline/`) — ingestion logic tightly coupled to pipeline runner
3. **Repositories** (`src/librarian/repositories/`) — some business logic leaked into data-access code

**Example of current problem:**
```python
# routers/documents.py - business logic mixed with HTTP concerns
@router.get("/api/v1/search/hybrid")
async def search_hybrid(q: str, limit: int = 10, db: Session = Depends(get_db)):
    # Business logic directly in handler
    keyword_results = db.execute(fts5_query(q))
    vector_results = chroma_client.query(embed(q))
    merged = rrf_merge(keyword_results, vector_results)
    return {"results": merged[:limit]}
```

**What we want:**
```python
# routers/documents.py - thin handler
@router.get("/api/v1/search/hybrid")
async def search_hybrid(q: str, limit: int = 10, search: SearchService = Depends()):
    results = await search.hybrid(query=q, limit=limit)
    return {"results": results}

# services/search.py - business logic
class SearchService:
    async def hybrid(self, query: str, limit: int = 10) -> list[SearchResult]:
        keyword_results = self.keyword_repo.search(query)
        vector_results = self.vector_store.search(query)
        merged = self._rrf_merge(keyword_results, vector_results)
        return merged[:limit]
```

---

## Target Architecture

```
┌──────────────────────────────────────────────────┐
│                 Interface Layer                   │
│   REST API    │    MCP Tools    │    CLI Commands │
│  (FastAPI)    │  (mcp SDK)      │    (Typer)      │
├──────────────────────────────────────────────────┤
│                 Service Layer                     │
│  DocumentService │ SearchService │ TagService     │
│  IngestService   │ StatsService  │                │
├──────────────────────────────────────────────────┤
│                 Data Access Layer                 │
│  Repositories (SQLAlchemy) │ ChromaDB Client      │
├──────────────────────────────────────────────────┤
│                 Storage Layer                     │
│       SQLite          │       ChromaDB            │
└──────────────────────────────────────────────────┘
```

---

## Services to Extract

### 1. `DocumentService`

**Location:** `src/librarian/services/document.py`

**Responsibilities:**
- Document CRUD operations
- Status transitions (pending → processing → processed / error)
- File operations (hash computation, path validation)
- Chunk management (create, update, delete chunks for a document)

**Methods to extract:**
```python
class DocumentService:
    async def create(self, file_path: str, metadata: dict) -> Document
    async def get(self, document_id: int) -> Document | None
    async def get_by_hash(self, file_hash: str) -> Document | None
    async def list(self, filters: DocumentFilters, pagination: Pagination) -> list[Document]
    async def update_status(self, document_id: int, status: DocumentStatus) -> Document
    async def delete(self, document_id: int) -> bool
    async def get_chunks(self, document_id: int) -> list[Chunk]
    async def compute_file_hash(self, file_path: str) -> str
    async def validate_file_path(self, file_path: str) -> bool
```

**Current code to migrate from:**
- `routers/documents.py` — document CRUD handlers
- `pipeline/ingest.py` — document creation logic
- `repositories/document.py` — move query methods to repo, business logic to service

---

### 2. `SearchService`

**Location:** `src/librarian/services/search.py`

**Responsibilities:**
- Keyword search orchestration (FTS5)
- Semantic search orchestration (Ollama + ChromaDB)
- Hybrid search with RRF merge
- Search result formatting

**Methods to extract:**
```python
class SearchService:
    async def keyword(self, query: str, limit: int, filters: SearchFilters) -> list[SearchResult]
    async def semantic(self, query: str, limit: int, filters: SearchFilters) -> list[SearchResult]
    async def hybrid(self, query: str, limit: int, filters: SearchFilters) -> list[SearchResult]
    async def _rrf_merge(self, keyword_results: list, semantic_results: list, k: int = 60) -> list[SearchResult]
```

**Current code to migrate from:**
- `routers/search.py` — all search endpoints
- `intelligence/embedder.py` — embedding logic (keep in intelligence, call from service)
- `storage/vector_store.py` — vector search (keep in storage, call from service)

**Graceful degradation:**
- If Ollama unavailable, semantic/hybrid search should fall back to keyword-only
- Log warning when falling back

---

### 3. `TagService`

**Location:** `src/librarian/services/tag.py`

**Responsibilities:**
- Tag CRUD operations
- Tag assignment to documents
- Bulk tag operations

**Methods to extract:**
```python
class TagService:
    async def create(self, name: str) -> Tag
    async def get(self, tag_id: int) -> Tag | None
    async def get_by_name(self, name: str) -> Tag | None
    async def list(self) -> list[Tag]
    async def add_to_document(self, document_id: int, tag_name: str) -> bool
    async def remove_from_document(self, document_id: int, tag_name: str) -> bool
    async def get_document_tags(self, document_id: int) -> list[Tag]
    async def bulk_add(self, document_ids: list[int], tag_name: str) -> int
```

**Current code to migrate from:**
- `routers/tags.py` — tag CRUD handlers
- `routers/documents.py` — tag assignment endpoints

---

### 4. `IngestService`

**Location:** `src/librarian/services/ingest.py`

**Responsibilities:**
- Upload handling (file validation, copying to inbox)
- Pipeline triggering
- Ingestion status tracking

**Methods to extract:**
```python
class IngestService:
    async def upload(self, file_path: str | None, content: bytes | None, filename: str) -> IngestResult
    async def trigger_pipeline(self, document_id: int) -> bool
    async def get_status(self, document_id: int) -> IngestStatus
    async def watch_directory(self, path: str, recursive: bool = True) -> WatchResult
```

**Current code to migrate from:**
- `pipeline/ingest.py` — upload and ingestion logic
- `routers/documents.py` — upload endpoint
- `watcher/observer.py` — file watching (keep in watcher, call from service)

**Security:**
- `upload()` must validate file paths against `allowed_parent_paths`
- `watch_directory()` must validate paths against boundaries

---

### 5. `StatsService`

**Location:** `src/librarian/services/stats.py`

**Responsibilities:**
- Library statistics aggregation
- Document counts by status
- Storage usage calculation
- Tag usage statistics

**Methods to extract:**
```python
class StatsService:
    async def get_library_stats(self) -> LibraryStats
    async def get_tag_stats(self) -> list[TagStats]
    async def get_storage_usage(self) -> StorageStats
```

**Current code to migrate from:**
- `routers/documents.py` — stats endpoint

---

## Implementation Order

Extract services in this order (most complex/valuable first):

1. **SearchService** (Medium effort, highest value for M7)
   - Used by most MCP tools
   - Has graceful degradation logic
   - Tests search functionality end-to-end

2. **DocumentService** (Medium effort)
   - Core CRUD for documents
   - Foundation for other services

3. **TagService** (Low effort)
   - Simple CRUD
   - Quick win

4. **IngestService** (Low effort)
   - Wrapper around existing pipeline
   - Security validation

5. **StatsService** (Low effort)
   - Simple aggregation
   - Quick win

---

## Migration Strategy

**For each service:**

1. **Create service file**
   ```bash
   touch src/librarian/services/__init__.py
   touch src/librarian/services/{document,search,tag,ingest,stats}.py
   ```

2. **Extract service class**
   - Define the class with async methods
   - Constructor injection for dependencies (repos, external clients)
   - Move business logic from handlers to service methods

3. **Update API handlers**
   - Add service as FastAPI dependency
   - Replace business logic with service calls
   - Keep only validation and response formatting

4. **Run tests**
   - All existing tests must pass
   - No functional changes

5. **Add service tests** (optional for M6.5, can be M7 work)
   - Unit tests for service methods
   - Mock dependencies

---

## File Structure After M6.5

```
src/librarian/
├── api/
│   ├── __init__.py
│   ├── main.py
│   └── routers/
│       ├── documents.py    # Thin handlers
│       ├── search.py       # Thin handlers
│       └── tags.py         # Thin handlers
├── services/
│   ├── __init__.py
│   ├── document.py         # NEW
│   ├── search.py           # NEW
│   ├── tag.py              # NEW
│   ├── ingest.py           # NEW
│   └── stats.py            # NEW
├── repositories/
│   ├── document.py
│   └── tag.py
├── intelligence/
│   ├── embedder.py
│   └── pipeline.py
├── storage/
│   └── vector_store.py
├── watcher/
│   └── observer.py
└── core/
    ├── config.py
    ├── database.py
    └── scheduler.py
```

---

## Success Criteria

1. ✅ All 5 service classes exist in `src/librarian/services/`
2. ✅ All business logic moved to services (handlers are thin)
3. ✅ All 83 existing tests continue to pass
4. ✅ Services are independently testable (constructor injection)
5. ✅ Clear boundaries: services own transactions, repos own queries
6. ✅ No functional changes — behavior is identical to M6

---

## Testing Commands

```bash
# Run all tests (must pass)
pytest

# Run with coverage
pytest --cov=src/librarian/services

# Run specific service tests (if added)
pytest tests/test_services/
```

---

## Dependencies (FastAPI)

Services will be injected via FastAPI's dependency system:

```python
# api/deps.py
from functools import lru_cache
from librarian.services.search import SearchService
from librarian.services.document import DocumentService

@lru_cache
def get_search_service() -> SearchService:
    return SearchService(
        keyword_repo=KeywordRepository(),
        vector_store=VectorStore(),
        embedder=Embedder()
    )

@lru_cache
def get_document_service() -> DocumentService:
    return DocumentRepository()

# routers/search.py
from api.deps import get_search_service

@router.get("/api/v1/search/hybrid")
async def search_hybrid(
    q: str,
    limit: int = 10,
    search: SearchService = Depends(get_search_service)
):
    results = await search.hybrid(query=q, limit=limit)
    return {"results": results}
```

---

## Notes

- **Don't change behavior** — M6.5 is refactoring only
- **Keep repositories thin** — they should only do queries, not business logic
- **Services own transactions** — each service method is a unit of work
- **Dependency injection** — services receive repos/clients in constructor
- **Async everywhere** — all service methods should be async

---

## Time Estimate

- SearchService: 4-6 hours
- DocumentService: 4-6 hours
- TagService: 2-3 hours
- IngestService: 2-3 hours
- StatsService: 1-2 hours
- Testing & cleanup: 2-3 hours

**Total: 15-23 hours (2-3 days)**

---

## References

- `docs/MILESTONES.md` — M6.5 section
- `docs/ARCHITECTURE.md` — ADR-008: Service Layer Design
- `docs/MCP-SPEC.md` — MCP tools that will call these services
