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
