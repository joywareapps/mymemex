# M6 Implementation: Semantic Search with Ollama + ChromaDB

**Project:** Librarian - Sovereign Document Intelligence Platform
**Milestone:** M6 - Vector embeddings and semantic search
**Effort:** High (expect 45-60 min)
**Location:** `~/code/librarian`

---

## Overview

Add semantic search capabilities using vector embeddings. This enables meaning-based search beyond keywords - "find documents about machine learning" will match documents discussing AI, neural networks, etc.

**Current Status (M1-M5):**
- ✅ File watching, text extraction, OCR
- ✅ FTS5 keyword search working
- ✅ 47 tests passing
- ✅ FastAPI REST API

**Goal (M6):**
- Vector embeddings via Ollama
- ChromaDB for vector storage
- Hybrid search (keyword + semantic)
- Graceful degradation when Ollama unavailable

---

## Prerequisites

**1. Ollama Installation (on office-pc):**
```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama
ollama serve

# Pull embedding model
ollama pull nomic-embed-text
```

**2. Verify Ollama is running (on office-pc):**
```bash
curl http://office-pc:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "test"}'
```

**3. Install Python dependencies:**
```bash
pip install chromadb litellm
```

---

## Architecture

```
┌─────────────────┐
│  Document Text  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      HTTP POST
│  Embedder       │──────────────────►  Ollama
│  (Python)       │  /api/embeddings   (nomic-embed-text)
└────────┬────────┘
         │ Vector (768 dim)
         ▼
┌─────────────────┐
│   ChromaDB      │  Persistent vector store
│   (embedded)    │  HNSW index for fast search
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Semantic       │  Query: "find AI papers"
│  Search API     │  Returns: docs about ML, neural nets, etc.
└─────────────────┘
```

---

## What to Implement

### 1. Embedder Module (`src/librarian/intelligence/embedder.py`)

Create a new file for embedding generation:

```python
"""Vector embeddings via Ollama."""
import asyncio
from typing import Optional
import structlog
import httpx

from ..config import LLMConfig

log = structlog.get_logger()


class Embedder:
    """Generate embeddings via Ollama HTTP API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
        self._model_available: Optional[bool] = None

    async def is_available(self) -> bool:
        """Check if Ollama is reachable and model is available."""
        if self._model_available is not None:
            return self._model_available

        try:
            # Check if Ollama is running
            resp = await self.client.get(f"{self.config.api_base}/api/tags")
            if resp.status_code != 200:
                self._model_available = False
                return False

            # Check if model is pulled
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]

            # Model might be "nomic-embed-text" or "nomic-embed-text:latest"
            model_base = self.config.model.split(":")[0]
            self._model_available = any(
                m.startswith(model_base) for m in model_names
            )

            if not self._model_available:
                log.warning(
                    "Embedding model not found in Ollama",
                    model=self.config.model,
                    available=model_names,
                )

            return self._model_available

        except Exception as e:
            log.warning("Ollama not reachable", error=str(e))
            self._model_available = False
            return False

    async def embed(self, text: str) -> Optional[list[float]]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            768-dimensional vector, or None if unavailable
        """
        if not await self.is_available():
            return None

        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            embedding = await loop.run_in_executor(
                None,
                self._embed_sync,
                text,
            )
            return embedding
        except Exception as e:
            log.error("Embedding failed", error=str(e), text_preview=text[:50])
            return None

    def _embed_sync(self, text: str) -> Optional[list[float]]:
        """Synchronous embedding call (runs in thread pool)."""
        import httpx

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.config.api_base}/api/embeddings",
                    json={
                        "model": self.config.model,
                        "prompt": text,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding")
        except Exception as e:
            log.error("Sync embedding failed", error=str(e))
            return None

    async def embed_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings (or None for failed items)
        """
        # Process sequentially to avoid overwhelming Ollama
        # Can be parallelized later with semaphore
        embeddings = []
        for text in texts:
            emb = await self.embed(text)
            embeddings.append(emb)
        return embeddings

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
```

### 2. Vector Store Wrapper (`src/librarian/storage/vector_store.py`)

Create a ChromaDB wrapper:

```python
"""ChromaDB vector store for semantic search."""
from typing import Optional
import uuid
import structlog
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from ..config import DatabaseConfig

log = structlog.get_logger()


class VectorStore:
    """ChromaDB wrapper for document embeddings."""

    def __init__(self, config: DatabaseConfig):
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb not installed. Run: pip install chromadb")

        self.config = config
        self.persist_dir = Path(config.path).parent / "chromadb"
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(self.persist_dir),
        ))

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

        log.info(
            "Vector store initialized",
            persist_dir=str(self.persist_dir),
            count=self.collection.count(),
        )

    def add(
        self,
        chunk_id: int,
        document_id: int,
        text: str,
        embedding: list[float],
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Add a chunk embedding to the vector store.

        Args:
            chunk_id: Database chunk ID
            document_id: Database document ID
            text: Chunk text
            embedding: Vector embedding
            metadata: Optional metadata

        Returns:
            Vector ID (UUID)
        """
        vector_id = str(uuid.uuid4())

        meta = metadata or {}
        meta.update({
            "chunk_id": chunk_id,
            "document_id": document_id,
        })

        self.collection.add(
            ids=[vector_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta],
        )

        return vector_id

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query vector
            n_results: Number of results
            where: Metadata filter (e.g., {"document_id": 5})

        Returns:
            List of results with chunk_id, document_id, text, distance
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, vector_id in enumerate(results["ids"][0]):
                formatted.append({
                    "vector_id": vector_id,
                    "chunk_id": results["metadatas"][0][i]["chunk_id"],
                    "document_id": results["metadatas"][0][i]["document_id"],
                    "text": results["documents"][0][i],
                    "distance": results["distances"][0][i],
                })

        return formatted

    def delete_by_document(self, document_id: int):
        """Delete all vectors for a document."""
        # ChromaDB doesn't have direct delete by metadata, so we query first
        results = self.collection.get(
            where={"document_id": document_id},
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            log.info("Deleted document vectors", document_id=document_id, count=len(results["ids"]))

    def count(self) -> int:
        """Get total number of vectors."""
        return self.collection.count()

    def persist(self):
        """Persist to disk."""
        self.client.persist()
```

### 3. Update Configuration (`src/librarian/config.py`)

Add AI configuration:

```python
class AIConfig(BaseSettings):
    """AI/LLM configuration (M6+)."""
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    embedding_batch_size: int = 8
    semantic_search_enabled: bool = True

class AppConfig(BaseSettings):
    # ... existing config ...

    ai: AIConfig = Field(default_factory=AIConfig)
```

### 4. Update Models (`src/librarian/storage/models.py`)

The `Chunk` model already has `has_embedding` and `vector_id` fields. Verify they exist:

```python
class Chunk(Base):
    # ... existing fields ...

    # Vector embedding fields (M6)
    has_embedding: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
```

If not present, add migration:
```bash
alembic revision --autogenerate -m "Add vector fields to chunks"
alembic upgrade head
```

### 5. Embedding Pipeline (`src/librarian/intelligence/pipeline.py`)

Create a new file for embedding pipeline:

```python
"""Embedding generation pipeline."""
import asyncio
from typing import Optional
import structlog

from ..config import AppConfig
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentRepository
from ..storage.vector_store import VectorStore
from .embedder import Embedder

log = structlog.get_logger()


async def embed_pending_chunks(config: AppConfig) -> int:
    """
    Generate embeddings for chunks that don't have them yet.

    Returns:
        Number of chunks embedded
    """
    if not config.ai.semantic_search_enabled:
        log.info("Semantic search disabled, skipping embeddings")
        return 0

    embedder = Embedder(config.llm)
    vector_store = VectorStore(config.database)

    if not await embedder.is_available():
        log.warning("Embedder not available, skipping")
        return 0

    embedded_count = 0

    async with get_session() as session:
        chunk_repo = ChunkRepository(session)
        doc_repo = DocumentRepository(session)

        # Get chunks without embeddings
        chunks = await chunk_repo.get_chunks_without_embeddings(limit=100)

        log.info("Embedding chunks", count=len(chunks))

        for chunk in chunks:
            # Generate embedding
            embedding = await embedder.embed(chunk.text)

            if embedding is None:
                log.warning("Failed to embed chunk", chunk_id=chunk.id)
                continue

            # Store in ChromaDB
            doc = await doc_repo.get_by_id(chunk.document_id)
            metadata = {
                "document_id": chunk.document_id,
                "page_number": chunk.page_number,
                "extraction_method": chunk.extraction_method,
            }

            vector_id = vector_store.add(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                embedding=embedding,
                metadata=metadata,
            )

            # Update chunk record
            await chunk_repo.update(
                chunk,
                has_embedding=True,
                vector_id=vector_id,
            )

            embedded_count += 1

            # Commit every 10 chunks
            if embedded_count % 10 == 0:
                await session.commit()
                log.info("Embedding progress", count=embedded_count)

        await session.commit()

    await embedder.close()
    vector_store.persist()

    log.info("Embedding complete", total=embedded_count)
    return embedded_count
```

### 6. Semantic Search API (`src/librarian/api/search.py`)

Add semantic search endpoint:

```python
# Add to existing search.py

from ..intelligence.embedder import Embedder
from ..storage.vector_store import VectorStore

@router.get("/semantic")
async def semantic_search(
    q: str,
    limit: int = 10,
    config: AppConfig = Depends(get_config),
):
    """
    Semantic search using vector embeddings.

    Returns chunks ranked by semantic similarity to query.
    """
    if not config.ai.semantic_search_enabled:
        raise HTTPException(503, "Semantic search disabled")

    embedder = Embedder(config.llm)
    vector_store = VectorStore(config.database)

    if not await embedder.is_available():
        raise HTTPException(503, "Embeddings not available (Ollama unreachable)")

    try:
        # Generate query embedding
        query_embedding = await embedder.embed(q)

        if query_embedding is None:
            raise HTTPException(500, "Failed to generate query embedding")

        # Search vector store
        results = vector_store.search(
            query_embedding=query_embedding,
            n_results=limit,
        )

        # Format response
        return {
            "query": q,
            "results": results,
            "total": len(results),
        }

    finally:
        await embedder.close()
```

### 7. Hybrid Search API (`src/librarian/api/search.py`)

Add hybrid search (keyword + semantic):

```python
@router.get("/hybrid")
async def hybrid_search(
    q: str,
    limit: int = 10,
    keyword_weight: float = 0.3,
    session: AsyncSession = Depends(get_session),
    config: AppConfig = Depends(get_config),
):
    """
    Hybrid search: combines FTS5 keyword search + semantic search.

    Args:
        q: Query string
        limit: Max results
        keyword_weight: Weight for keyword results (0.0-1.0, rest goes to semantic)

    Returns:
        Merged and ranked results
    """
    if not config.ai.semantic_search_enabled:
        # Fallback to keyword-only
        return await keyword_search(q, limit, session)

    # Get keyword results
    keyword_results = await _keyword_search_internal(q, limit * 2, session)

    # Get semantic results
    embedder = Embedder(config.llm)
    vector_store = VectorStore(config.database)

    try:
        query_embedding = await embedder.embed(q)
        if query_embedding:
            semantic_results = vector_store.search(
                query_embedding=query_embedding,
                n_results=limit * 2,
            )
        else:
            semantic_results = []

    finally:
        await embedder.close()

    # Merge results with Reciprocal Rank Fusion
    merged = _reciprocal_rank_fusion(
        keyword_results,
        semantic_results,
        keyword_weight,
    )

    return {
        "query": q,
        "results": merged[:limit],
        "total": len(merged[:limit]),
        "keyword_results": len(keyword_results),
        "semantic_results": len(semantic_results),
    }


def _reciprocal_rank_fusion(
    keyword_results: list,
    semantic_results: list,
    keyword_weight: float,
    k: int = 60,
) -> list:
    """
    Merge results using Reciprocal Rank Fusion (RRF).

    RRF score = 1 / (k + rank)
    """
    scores = {}

    # Score keyword results
    for rank, result in enumerate(keyword_results):
        chunk_id = result.get("chunk_id") or result.get("id")
        score = keyword_weight / (k + rank + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + score

    # Score semantic results
    semantic_weight = 1.0 - keyword_weight
    for rank, result in enumerate(semantic_results):
        chunk_id = result["chunk_id"]
        score = semantic_weight / (k + rank + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + score

    # Sort by score
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Build final results (would need to fetch from DB)
    # For now, return IDs with scores
    return [
        {"chunk_id": chunk_id, "score": score}
        for chunk_id, score in sorted_ids
    ]
```

### 8. Update Dependencies (`pyproject.toml`)

Add AI dependencies:

```toml
[project.optional-dependencies]
ai = [
    "chromadb>=0.6",
    "litellm>=1.60",
]
```

### 9. Background Embedding Task (`src/librarian/core/scheduler.py`)

Create scheduler for periodic embedding:

```python
"""Background task scheduler."""
import asyncio
import structlog

from ..config import AppConfig
from ..intelligence.pipeline import embed_pending_chunks

log = structlog.get_logger()


async def embedding_scheduler(config: AppConfig):
    """
    Periodically generate embeddings for new chunks.

    Runs every 60 seconds.
    """
    while True:
        try:
            await asyncio.sleep(60)  # Run every minute

            count = await embed_pending_chunks(config)

            if count > 0:
                log.info("Background embedding complete", chunks=count)

        except asyncio.CancelledError:
            log.info("Embedding scheduler stopping")
            break
        except Exception as e:
            log.error("Embedding scheduler error", error=str(e))
            await asyncio.sleep(60)  # Wait before retry
```

### 10. Update App Startup (`src/librarian/app.py`)

Start embedding scheduler:

```python
from .core.scheduler import embedding_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    config = app.state.config

    # ... existing startup ...

    # Start embedding scheduler (if AI enabled)
    if config.ai.semantic_search_enabled:
        scheduler_task = asyncio.create_task(embedding_scheduler(config))
        app.state.scheduler_task = scheduler_task

    yield

    # ... existing shutdown ...

    if hasattr(app.state, "scheduler_task"):
        app.state.scheduler_task.cancel()
```

---

## Testing

### 1. Create Test File (`tests/test_embedder.py`)

```python
"""Tests for embedding functionality."""
import pytest
from librarian.intelligence.embedder import Embedder
from librarian.config import LLMConfig


@pytest.mark.asyncio
async def test_embedder_unavailable():
    """Embedder should handle unavailable Ollama gracefully."""
    config = LLMConfig(
        provider="ollama",
        model="nomic-embed-text",
        api_base="http://office-pc:99999",  # Wrong port
    )
    embedder = Embedder(config)

    # Should not be available
    assert not await embedder.is_available()

    # Should return None for embedding
    embedding = await embedder.embed("test text")
    assert embedding is None

    await embedder.close()


@pytest.mark.asyncio
async def test_embedder_embed_text(test_config):
    """Test embedding generation (requires Ollama running)."""
    if not test_config.ai.semantic_search_enabled:
        pytest.skip("Semantic search disabled in test config")

    embedder = Embedder(test_config.llm)

    if not await embedder.is_available():
        pytest.skip("Ollama not available")

    embedding = await embedder.embed("This is a test document about machine learning.")

    assert embedding is not None
    assert len(embedding) == 768  # nomic-embed-text dimension

    await embedder.close()
```

### 2. Create Vector Store Tests (`tests/test_vector_store.py`)

```python
"""Tests for vector store."""
import pytest
from pathlib import Path
from librarian.storage.vector_store import VectorStore
from librarian.config import DatabaseConfig


@pytest.fixture
def vector_store(tmp_dir):
    """Create a test vector store."""
    config = DatabaseConfig(path=str(tmp_dir / "test.db"))
    return VectorStore(config)


def test_vector_store_add_and_search(vector_store):
    """Test adding and searching vectors."""
    # Add a vector
    embedding = [0.1] * 768  # Dummy embedding
    vector_id = vector_store.add(
        chunk_id=1,
        document_id=1,
        text="Test document about AI",
        embedding=embedding,
    )

    assert vector_id is not None

    # Search
    results = vector_store.search(
        query_embedding=embedding,
        n_results=5,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == 1


def test_vector_store_count(vector_store):
    """Test vector count."""
    assert vector_store.count() == 0

    embedding = [0.1] * 768
    vector_store.add(1, 1, "test", embedding)

    assert vector_store.count() == 1
```

---

## Implementation Steps

1. **Create embedder module** (`src/librarian/intelligence/embedder.py`)
2. **Create vector store** (`src/librarian/storage/vector_store.py`)
3. **Update config** (add AIConfig)
4. **Check/update models** (ensure has_embedding, vector_id fields exist)
5. **Create embedding pipeline** (`src/librarian/intelligence/pipeline.py`)
6. **Add semantic search API** (`src/librarian/api/search.py`)
7. **Add hybrid search API** (`src/librarian/api/search.py`)
8. **Create scheduler** (`src/librarian/core/scheduler.py`)
9. **Update app startup** (`src/librarian/app.py`)
10. **Add tests** (`tests/test_embedder.py`, `tests/test_vector_store.py`)
11. **Run tests:** `pytest tests/test_embedder.py tests/test_vector_store.py -v`

---

## Validation Criteria

✅ Ollama reachable and model available
✅ Embeddings generated successfully (768 dimensions)
✅ ChromaDB stores and retrieves vectors
✅ Semantic search returns relevant results
✅ Hybrid search combines keyword + semantic
✅ Background scheduler runs without errors
✅ Graceful degradation when Ollama unavailable
✅ Tests pass (with/without Ollama)

---

## Configuration Example

```yaml
# config.yaml
llm:
  provider: ollama
  model: nomic-embed-text
  api_base: http://office-pc:11434

ai:
  embedding_model: nomic-embed-text
  embedding_dimension: 768
  embedding_batch_size: 8
  semantic_search_enabled: true

database:
  path: ~/.local/share/librarian/librarian.db
```

---

## Usage Examples

**1. Start Ollama (on office-pc):**
```bash
# Run on office-pc
ollama serve
ollama pull nomic-embed-text
```

**2. Start Librarian:**
```bash
librarian serve
```

**3. Semantic Search:**
```bash
curl "http://localhost:8000/api/v1/search/semantic?q=machine+learning&limit=10"
```

**4. Hybrid Search:**
```bash
curl "http://localhost:8000/api/v1/search/hybrid?q=AI+research&limit=10"
```

**5. Check Embeddings:**
```bash
curl "http://localhost:8000/api/v1/system/stats"
```

---

## Important Notes

1. **Ollama Host:** Ollama runs on `office-pc` (not localhost). Ensure network connectivity.
2. **Batch Processing:** Embeddings are CPU-intensive. Process in batches.
3. **Memory:** ChromaDB uses mmap, doesn't pin RAM.
4. **Latency:** Embedding generation ~50-100ms per chunk.
5. **Fallback:** System works without Ollama (keyword-only mode).
6. **Persistence:** ChromaDB data stored in `~/.local/share/librarian/chromadb/`.

---

## Expected Outcome

After M6:
- ✅ Semantic search available
- ✅ Hybrid search (keyword + semantic)
- ✅ Graceful degradation without Ollama
- ✅ Background embedding generation
- ✅ Vector similarity ranking
- ✅ ChromaDB persistence

---

## Files to Create/Modify

**Create:**
- `src/librarian/intelligence/__init__.py` (new package)
- `src/librarian/intelligence/embedder.py` (~150 LOC)
- `src/librarian/intelligence/pipeline.py` (~80 LOC)
- `src/librarian/storage/vector_store.py` (~120 LOC)
- `src/librarian/core/scheduler.py` (~30 LOC)
- `tests/test_embedder.py` (~50 LOC)
- `tests/test_vector_store.py` (~40 LOC)

**Modify:**
- `src/librarian/config.py` (add AIConfig, ~20 LOC)
- `src/librarian/api/search.py` (add semantic/hybrid endpoints, ~80 LOC)
- `src/librarian/app.py` (start scheduler, ~10 LOC)
- `src/librarian/storage/models.py` (verify vector fields, ~5 LOC)

**Total:** ~585 lines of new/modified code

---

Start with the embedder and vector store, then integrate into the API. Test with Ollama running to validate the full flow.

Good luck! 🚀
