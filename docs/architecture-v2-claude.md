# Architecture Proposal v2: Claude Synthesis

**Source:** Claude (Opus 4.6) — synthesizing all prior proposals + constraints
**Date:** 2026-02-16
**Status:** Implementation-ready v2 proposal

---

## Executive Summary

This proposal synthesizes ideas from the Gemini, Claude v1, Gemini v2, and Reasoner v2 proposals into a single implementation-ready architecture that **strictly obeys the constraint document**. It also challenges several assumptions made by prior proposals.

### Key Decisions at a Glance

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AI integration | All via HTTP APIs (LiteLLM + httpx) | Constraint 1.1 — no ML frameworks |
| Local OCR | Tesseract (built-in) + OCR service endpoint (optional) | No ML deps; mirrors LLM externalization pattern |
| PDF text | PyMuPDF native extraction first | Skips OCR for ~60% of PDFs |
| Embeddings | Ollama `/api/embed` via httpx/LiteLLM | No sentence-transformers |
| LLM | LiteLLM unified interface | Provider-agnostic |
| Metadata DB | SQLite + FTS5 | Zero-config, portable, ACID |
| Vector DB | ChromaDB (embedded, persistent) | Embedded, persistent, good Python API |
| Task queue | SQLite-backed (upgrade path to Redis) | Zero extra deps for NAS |
| Search | Hybrid vector + FTS5 with RRF | Best of both worlds; FTS5 works offline |
| Process model | Single process, async + ProcessPoolExecutor for OCR | Minimal RAM on NAS |
| Dedup | Two-phase: xxhash pre-filter + SHA-256 canonical | 15 min → 2 sec startup scan |

### Assumptions Challenged

1. **"PaddleOCR has a PyTorch dependency"** (Reasoner v2) — Wrong. PaddleOCR depends on *PaddlePaddle*, not PyTorch. But PaddlePaddle is still an ML framework, so PaddleOCR still violates the constraint. The Reasoner reached the right conclusion for the wrong reason.

2. **"Tesseract is the only local OCR option"** (Reasoner v2) — Incomplete. The constraint forbids ML frameworks *as direct dependencies of the application*. We can externalize OCR the same way we externalize LLM: run PaddleOCR/Surya/EasyOCR as a separate container or service, call it via HTTP. This gives users PaddleOCR accuracy without violating constraints.

3. **"Redis is needed for production queuing"** (Claude v1) — Premature. For a single-user NAS system processing documents sequentially, SQLite WAL-mode handles the queue just fine. Redis adds operational complexity (another container, config, monitoring) with no benefit at this scale. We provide an upgrade path, not a requirement.

4. **"`arq` for task queue"** (Claude v1) — Unnecessary dependency. A SQLite-backed queue with `asyncio` workers is ~150 LOC, zero extra deps, and perfectly adequate. The task queue table in SQLite gives us persistence, retryability, and prioritization for free.

5. **"`tiktoken` for token counting"** (Claude v1, Reasoner v2) — Over-specified. tiktoken is tied to OpenAI tokenizers. For chunking purposes, a simple word-count heuristic (`len(text.split()) * 1.3`) or a configurable `max_chars` is sufficient and avoids a Rust-compiled dependency. If exact token counts matter (for LLM context windows), LiteLLM provides `token_counter()`.

6. **"LlamaIndex/LangChain for the agentic layer"** (Gemini v1) — Over-engineered. Librarian's "agents" are prompt chains: classification = one LLM call with structured output; RAG = embed query → retrieve → synthesize. A thin wrapper around LiteLLM with Jinja2 templates (~200 LOC) is simpler, faster, and infinitely more debuggable.

7. **"`unstructured` for document parsing"** (Gemini v1) — Kitchen-sink. It installs 50+ transitive dependencies, is slow, and hides failures behind abstractions. PyMuPDF + Tesseract compose better, fail more clearly, and give us control over the OCR→text→chunk pipeline.

---

## 1. Python Libraries with Justification

### 1.1 Core Framework & Runtime

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `fastapi` | 0.115+ | HTTP API + WebSocket | Async-native, auto OpenAPI docs, Pydantic integration, industry standard |
| `uvicorn` | 0.34+ | ASGI server | Production-grade, works with FastAPI, supports graceful shutdown |
| `pydantic` | 2.x | Config, validation, schemas | Type safety; already a FastAPI dep; use for config parsing too |
| `pydantic-settings` | 2.x | Settings from env/YAML | Hierarchical config: defaults → YAML → env vars |
| `typer` | 0.15+ | CLI interface | Same ecosystem as FastAPI; auto --help; consistent patterns |
| `structlog` | 25.x | Structured logging | JSON in prod for log aggregation, pretty in dev; context binding |
| `alembic` | 1.14+ | Database migrations | Schema evolution is essential; SQLAlchemy integration |

### 1.2 File Watching & Ingestion

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `watchdog` | 6.x | Filesystem events | Cross-platform, inotify on Linux, polling fallback for NFS/SMB |
| `python-magic` | 0.4+ | MIME type detection | `libmagic` wrapper; reliable file type detection beyond extension |
| `xxhash` | 3.x | Fast hash pre-filter | 10x faster than SHA-256; pre-check on first 4KB + file size |
| `hashlib` (stdlib) | — | SHA-256 canonical hash | Cryptographic dedup; already in stdlib |

**Design: two-phase hashing.** On startup, the watcher must verify all known files. SHA-256 on 50K files (avg 2MB, ~100GB total) takes ~15 minutes. Instead:

```python
import xxhash
import hashlib

def quick_fingerprint(path: str) -> str:
    """Fast pre-filter: file size + xxhash of first 4KB. ~2 sec for 50K files."""
    stat = os.stat(path)
    with open(path, "rb") as f:
        head = f.read(4096)
    return f"{stat.st_size}:{xxhash.xxh64(head).hexdigest()}"

def canonical_hash(path: str, buf_size: int = 1 << 20) -> str:
    """Full SHA-256. Only computed for files that pass pre-filter as new."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(buf_size):
            h.update(chunk)
    return h.hexdigest()
```

### 1.3 Document Processing & OCR

| Library | Version | Purpose | ML Framework Dep? | Constraint |
|---------|---------|---------|-------------------|------------|
| `pymupdf` (fitz) | 1.25+ | PDF text extraction & page rendering | No | Compliant |
| `pytesseract` | 0.3+ | Local OCR (built-in) | No (calls Tesseract binary) | Compliant |
| `Pillow` | 11.x | Image preprocessing | No | Compliant |
| `pdf2image` | 1.17+ | PDF → image for OCR | No (calls poppler) | Compliant |
| `boto3` | 1.x | AWS Textract (cloud fallback) | No | Compliant |

**What about PaddleOCR?** PaddleOCR depends on PaddlePaddle (an ML framework), which violates Constraint 1.1. However, we can offer PaddleOCR accuracy without violating constraints by externalizing it:

```
┌─────────────────┐         ┌──────────────────────┐
│   Librarian     │  HTTP   │  OCR Service          │
│   (no ML deps)  │◄───────►│  (PaddleOCR container)│
│                 │         │  or Surya, EasyOCR    │
└─────────────────┘         └──────────────────────┘
```

The OCR service endpoint is configurable — the same pattern as the LLM endpoint:

```yaml
ocr:
  primary: tesseract                    # Built-in, no extra deps
  service_url: null                     # Optional: http://ocr-server:8080/ocr
  cloud_fallback:
    provider: aws_textract              # Optional: cloud fallback
```

**OCR pipeline decision tree:**

```python
async def extract_text(doc_path: str, page_num: int) -> TextResult:
    """Extract text from a single page, choosing the best available method."""

    # Phase 1: Try native PDF text extraction (instant, free)
    text = pymupdf_extract_page_text(doc_path, page_num)
    if len(text.strip()) >= 50:
        return TextResult(text=text, engine="pymupdf_native", confidence=1.0)

    # Phase 2: Try external OCR service if configured (best accuracy)
    if config.ocr.service_url:
        image = render_page_to_image(doc_path, page_num, dpi=300)
        result = await call_ocr_service(config.ocr.service_url, image)
        if result.confidence >= config.ocr.confidence_threshold:
            return result

    # Phase 3: Fall back to built-in Tesseract (always available)
    image = render_page_to_image(doc_path, page_num, dpi=300)
    result = tesseract_ocr(image, lang=config.ocr.language)
    if result.confidence >= config.ocr.confidence_threshold:
        return result

    # Phase 4: Queue for cloud OCR if enabled and confidence too low
    if config.ocr.cloud_fallback and config.privacy.allows_cloud(doc_path):
        await queue_cloud_ocr(doc_path, page_num)
        return TextResult(text=result.text, engine="tesseract", confidence=result.confidence,
                          cloud_pending=True)

    return result
```

### 1.4 Text Processing & Chunking

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `ftfy` | 6.x | Text cleanup | Fixes mojibake, encoding issues from OCR. Small, focused. |
| `langdetect` | 1.0+ | Language detection | Routes to correct Tesseract language pack; filters for language-specific search |
| `dateparser` | 1.2+ | Date extraction | Extract document dates from content (multi-format, multi-language) |

**Chunking: custom implementation (~80 LOC), no library.** Every chunking library (LangChain, LlamaIndex) is either too opinionated or pulls in heavy deps. Our needs are specific:

```python
import re

def chunk_text(
    text: str,
    max_chars: int = 1500,        # ~375 tokens at 4 chars/token
    overlap_chars: int = 200,     # ~50 tokens overlap
    page_number: int | None = None,
) -> list[dict]:
    """Recursive text splitter. Splits on paragraphs, then lines, then sentences."""
    if len(text) <= max_chars:
        return [{"text": text, "page_number": page_number}]

    # Try splitting on double newlines (paragraphs)
    chunks = _split_on_separator(text, "\n\n", max_chars, overlap_chars)
    if chunks:
        return [{"text": c, "page_number": page_number} for c in chunks]

    # Fall back to single newlines
    chunks = _split_on_separator(text, "\n", max_chars, overlap_chars)
    if chunks:
        return [{"text": c, "page_number": page_number} for c in chunks]

    # Fall back to sentence boundaries
    chunks = _split_on_separator(text, r"(?<=[.!?])\s+", max_chars, overlap_chars)
    if chunks:
        return [{"text": c, "page_number": page_number} for c in chunks]

    # Last resort: hard split on max_chars
    return [{"text": text[i:i + max_chars], "page_number": page_number}
            for i in range(0, len(text), max_chars - overlap_chars)]


def _split_on_separator(
    text: str, sep: str, max_chars: int, overlap_chars: int
) -> list[str] | None:
    """Split text on separator, merging small segments. Returns None if can't split."""
    parts = re.split(sep, text) if sep.startswith("(") else text.split(sep)
    if len(parts) <= 1:
        return None

    chunks = []
    current = ""
    for part in parts:
        candidate = (current + sep + part).strip() if current else part.strip()
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            # Overlap: keep tail of previous chunk
            current = current[-overlap_chars:] + sep + part if overlap_chars else part
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks if len(chunks) > 1 else None
```

**Why not `tiktoken`?** tiktoken requires a compiled Rust extension and is specific to OpenAI tokenizers. For chunking, character count with a conservative ratio (`max_chars=1500` ≈ 375 tokens) is simple and model-agnostic. When exact token counts matter (LLM context window sizing), use `litellm.token_counter(model, text)` which handles model-specific tokenization.

### 1.5 Embeddings & Vector Store

| Library | Version | Purpose | Constraint |
|---------|---------|---------|------------|
| `chromadb` | 0.6+ | Vector storage (embedded, persistent) | Compliant (no ML deps) |
| `httpx` | 0.28+ | Async HTTP client | Compliant |
| `litellm` | 1.x | Unified LLM/embedding API | Compliant (HTTP-only) |

**Embedding model:** `nomic-embed-text:latest` via Ollama (768-dim, 8192-token context window).

```python
import httpx
import litellm

class EmbeddingService:
    """Generates embeddings via external HTTP API. No ML frameworks in-process."""

    def __init__(self, config):
        self.config = config
        self._client = httpx.AsyncClient(timeout=30.0)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Uses LiteLLM for provider abstraction."""
        response = await litellm.aembedding(
            model=f"ollama/{self.config.ai.embedding.model}",
            input=texts,
            api_base=self.config.ai.embedding.base_url,
        )
        return [item["embedding"] for item in response.data]

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text. For query-time embedding."""
        results = await self.embed_texts([text])
        return results[0]

    async def health_check(self) -> bool:
        """Check if the embedding service is reachable."""
        try:
            await self.embed_single("health check")
            return True
        except Exception:
            return False
```

### 1.6 LLM & Prompt Layer

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `litellm` | 1.x | Unified LLM API | Supports 100+ providers; retries; fallback chains; streaming |
| `jinja2` | 3.x | Prompt templates | Battle-tested; already a FastAPI dep; logic-free templates |

**Why not LlamaIndex/LangChain?** Librarian's "agents" are three prompt templates:

1. **Classify**: "Given this text, return JSON with category, tags, summary, date"
2. **Query (RAG)**: "Given these document chunks, answer this question with citations"
3. **File suggestion**: "Given this document's content and these existing folders, suggest a location"

Each is a single LLM call with structured output. A framework that abstracts this adds 5000+ LOC of dependency for 200 LOC of value.

```python
# llm/client.py
import litellm
from jinja2 import Environment, PackageLoader

class LLMClient:
    """Thin wrapper around LiteLLM with Jinja2 prompt templates."""

    def __init__(self, config):
        self.config = config
        self.templates = Environment(loader=PackageLoader("librarian", "llm/prompts"))

    async def classify(self, text: str) -> dict:
        """Classify a document. Returns {category, tags, summary, date}."""
        prompt = self.templates.get_template("classify.j2").render(text=text[:3000])
        response = await litellm.acompletion(
            model=self.config.ai.llm.model,
            messages=[{"role": "user", "content": prompt}],
            api_base=self.config.ai.llm.base_url,
            response_format={"type": "json_object"},
            timeout=self.config.ai.llm.timeout,
        )
        return json.loads(response.choices[0].message.content)

    async def rag_query(self, query: str, chunks: list[dict]) -> dict:
        """RAG: synthesize an answer from retrieved chunks."""
        prompt = self.templates.get_template("query.j2").render(
            query=query, chunks=chunks
        )
        response = await litellm.acompletion(
            model=self.config.ai.llm.model,
            messages=[{"role": "user", "content": prompt}],
            api_base=self.config.ai.llm.base_url,
            timeout=self.config.ai.llm.timeout,
        )
        return {"answer": response.choices[0].message.content}

    async def health_check(self) -> bool:
        try:
            await litellm.acompletion(
                model=self.config.ai.llm.model,
                messages=[{"role": "user", "content": "hi"}],
                api_base=self.config.ai.llm.base_url,
                max_tokens=1,
                timeout=5,
            )
            return True
        except Exception:
            return False
```

### 1.7 Database

| Library | Version | Purpose | Why This One |
|---------|---------|---------|--------------|
| `sqlalchemy` | 2.x | ORM + connection management | Type-safe queries, async support, 2.0-style is clean |
| `aiosqlite` | 0.20+ | Async SQLite driver | Non-blocking DB access from async FastAPI |
| `alembic` | 1.14+ | Schema migrations | Essential for evolving schema across releases |

### 1.8 Testing & Development

| Library | Version | Purpose |
|---------|---------|---------|
| `pytest` | 8.x | Test runner |
| `pytest-asyncio` | 0.25+ | Async test support |
| `pytest-cov` | 6.x | Coverage reporting |
| `ruff` | 0.9+ | Linting + formatting (replaces black, isort, flake8) |
| `mypy` | 1.x | Static type checking |
| `pre-commit` | 4.x | Git hooks |

### 1.9 Constraint Compliance Summary

| Library | Gemini v1 | Claude v1 | Reasoner v2 | This Proposal | Compliant? |
|---------|-----------|-----------|-------------|---------------|------------|
| `sentence-transformers` | Yes | No | No | **No** | **NO** (PyTorch) |
| `transformers` | — | — | No | **No** | **NO** (PyTorch) |
| `unstructured` | Yes | No | No | **No** | Bloated, opaque |
| `paddleocr` | Yes | Yes | No | **No (direct)**; yes as external service | **NO** as dep (PaddlePaddle) |
| `llama-index` | Yes | No | No | **No** | Over-engineered |
| `pymupdf` | No | Yes | Yes | **Yes** | Yes |
| `pytesseract` | No | Yes | Yes | **Yes** | Yes |
| `litellm` | No | Yes | Yes | **Yes** | Yes |
| `chromadb` | Yes | Yes | Yes | **Yes** | Yes |
| `watchdog` | Yes | Yes | Yes | **Yes** | Yes |
| `tiktoken` | No | Yes | Yes | **No** | Not needed |
| `arq` | No | Yes | No | **No** | Not needed initially |

---

## 2. Data Flow Architecture

### 2.1 Ingestion Pipeline

```
                        ┌────────────────────────┐
                        │   Watched Directories   │
                        │  /mnt/nas/documents     │
                        │  /mnt/nas/scans         │
                        └───────────┬────────────┘
                                    │
                                    │ inotify / polling (watchdog)
                                    ▼
                        ┌────────────────────────┐
                        │     File Watcher        │
                        │                         │
                        │  Filters:               │
                        │  - Supported extensions │
                        │  - Ignore patterns      │
                        │  - Debounce (2 sec)     │
                        │  - Min file size        │
                        └───────────┬────────────┘
                                    │
                                    │ (file_path, event_type)
                                    ▼
                        ┌────────────────────────┐
                        │    Dedup Pre-Check      │
                        │                         │
                        │  1. file_size           │
                        │  2. xxhash(first 4KB)   │
                        │  3. Lookup in SQLite    │
                        └───────────┬────────────┘
                                    │
                             ┌──────┴──────┐
                             │             │
                        Known file    New/changed
                             │             │
                             ▼             ▼
                   ┌──────────────┐ ┌──────────────────┐
                   │ Link new     │ │   Task Queue     │
                   │ file_path to │ │ (SQLite table)   │
                   │ existing doc │ │                  │
                   └──────────────┘ │ Priorities:      │
                                    │  10: user upload │
                                    │   5: watcher     │
                                    │   1: backfill    │
                                    └────────┬─────────┘
                                             │
                                             ▼
                          ┌───────────────────────────────┐
                          │       Ingestion Worker        │
                          │    (async, max N concurrent)  │
                          │                               │
                          │  1. Compute SHA-256 full hash │
                          │  2. MIME type detection       │
                          │  3. Privacy policy check      │
                          │  4. Language detection        │
                          └──────────────┬────────────────┘
                                         │
                          ┌──────────────┴───────────────┐
                          │                              │
                     Has embedded text             Scanned/Image
                     (born-digital PDF)            (needs OCR)
                          │                              │
                          ▼                              ▼
                ┌─────────────────┐         ┌──────────────────────┐
                │   PyMuPDF       │         │    OCR Router        │
                │  native text    │         │                      │
                │  extraction     │         │  if service_url:     │
                │  (instant)      │         │    → External OCR    │
                │                 │         │  else:               │
                │  Skips OCR for  │         │    → Tesseract       │
                │  ~60% of PDFs   │         │  if conf < threshold │
                │                 │         │    AND cloud allowed: │
                └────────┬────────┘         │    → Queue cloud OCR │
                         │                  └──────────┬───────────┘
                         │                             │
                         └──────────┬──────────────────┘
                                    │
                                    │ raw text per page
                                    ▼
                          ┌─────────────────────┐
                          │   Text Pipeline     │
                          │                     │
                          │  1. ftfy cleanup     │
                          │  2. Language detect  │
                          │  3. Chunk (1500 ch)  │
                          │  4. Date extraction  │
                          └──────────┬──────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                          ▼                     ▼
                ┌──────────────────┐   ┌────────────────────┐
                │     SQLite       │   │  Queue: embed task │
                │                  │   │  (if LLM available) │
                │  - document row  │   └─────────┬──────────┘
                │  - chunk rows    │             │
                │  - file_paths    │             │ async worker
                │  - FTS5 index    │             ▼
                │  - processing_log│   ┌────────────────────┐
                └──────────────────┘   │   Ollama / LiteLLM │
                                       │   /api/embed       │
                                       └─────────┬──────────┘
                                                  │ vectors
                                                  ▼
                                       ┌────────────────────┐
                                       │     ChromaDB       │
                                       │  - chunk vectors   │
                                       │  - chunk metadata  │
                                       └────────────────────┘
```

**Key insight:** Text extraction and SQLite storage happen synchronously. Embedding is a separate queued task. This means:
- FTS5 keyword search works immediately after ingestion (no LLM needed)
- Semantic search becomes available when embeddings complete
- If Ollama is down, documents are still searchable by keyword

### 2.2 Query Pipeline

```
    User Query
    "Does my insurance cover rentals?"
         │
         ▼
┌─────────────────────┐
│   Query Router      │
│                     │
│ search_mode =       │
│   hybrid / vector / │
│   keyword           │
└──────────┬──────────┘
           │
     ┌─────┴──────────────────────────────┐
     │                                    │
     ▼                                    ▼
┌──────────────────┐             ┌──────────────────┐
│ Vector Search    │             │ FTS5 Keyword     │
│ (if LLM avail)  │             │ Search           │
│                  │             │ (always works)   │
│ 1. Embed query   │             │                  │
│    via Ollama    │             │ SELECT ... FROM  │
│ 2. ChromaDB      │             │ chunks_fts       │
│    similarity    │             │ WHERE chunks_fts │
│    (top K)       │             │ MATCH ?          │
│ 3. Metadata      │             │                  │
│    filtering     │             │                  │
└────────┬─────────┘             └────────┬─────────┘
         │                                │
         │  vector_results                │  keyword_results
         │                                │
         └────────────┬───────────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │ Reciprocal Rank  │
            │ Fusion (RRF)     │
            │                  │
            │ Merge & re-rank  │
            │ results from     │
            │ both sources     │
            └────────┬─────────┘
                     │
                     ▼
           ┌──────────────────┐
           │ RAG Synthesis    │
           │ (if LLM avail)  │
           │                  │
           │ Context: top     │
           │   chunks         │
           │ LLM: synthesize  │
           │   answer         │
           │ Extract: source  │
           │   citations      │
           └────────┬─────────┘
                    │
                    ▼
           ┌──────────────────┐
           │    Response      │
           │                  │
           │ answer: "..."    │
           │ sources: [...]   │
           │ search_mode: ... │
           │ degraded: false  │
           │ query_time_ms: . │
           └──────────────────┘
```

**Reciprocal Rank Fusion implementation:**

```python
def reciprocal_rank_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int = 60,
    vector_weight: float = 1.0,
    keyword_weight: float = 1.0,
) -> list[dict]:
    """
    Merge results from vector and keyword search using RRF.

    RRF score = sum( weight / (k + rank) ) for each result list.
    k=60 is the standard constant from the original RRF paper.
    """
    scores: dict[str, float] = {}
    all_results: dict[str, dict] = {}

    for rank, result in enumerate(vector_results):
        chunk_id = result["vector_id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + vector_weight / (k + rank + 1)
        all_results[chunk_id] = result

    for rank, result in enumerate(keyword_results):
        chunk_id = result["vector_id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + keyword_weight / (k + rank + 1)
        if chunk_id not in all_results:
            all_results[chunk_id] = result

    # Sort by fused score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {**all_results[chunk_id], "rrf_score": score}
        for chunk_id, score in ranked
    ]
```

### 2.3 Classification Flow

```
New Document Completed Text Extraction
         │
         ▼
┌─────────────────────────┐
│ Classification Eligible?│
│                         │
│ - classification enabled│
│   in config?            │
│ - document not already  │
│   classified?           │
│ - LLM available?        │
└──────────┬──────────────┘
           │ Yes
           ▼
┌──────────────────────────────────────────┐
│ Prepare Classification Input             │
│                                          │
│  - First 2 chunks of document text       │
│  - If doc > 10 pages: first + last chunk │
│  - Existing folder path (context)        │
│  - File name (often informative)         │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ LLM Call (via LiteLLM)                   │
│                                          │
│ Prompt: classify.j2                      │
│ Response format: JSON                    │
│                                          │
│ Expected output:                         │
│ {                                        │
│   "category": "insurance",              │
│   "tags": ["auto", "policy", "2024"],   │
│   "summary": "Auto insurance policy...",│
│   "document_date": "2024-03-15",        │
│   "suggested_title": "Auto Insurance    │
│    Policy - State Farm"                  │
│ }                                        │
│                                          │
│ Cost: 1 LLM call per document            │
│ Model: configurable (default: small      │
│   model like llama3.2:1b for speed)      │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ Update Database                          │
│                                          │
│ 1. Set category on document              │
│ 2. Create/link tags (auto source)        │
│ 3. Set summary                           │
│ 4. Set extracted_date                    │
│ 5. Log to processing_log                 │
│ 6. Notify via WebSocket                  │
└──────────────────────────────────────────┘
```

---

## 3. Database Schema

### 3.1 SQLite Schema (Content-Addressed)

```sql
-- ============================================================
-- Core document identity (content-addressed, not path-addressed)
-- A document is identified by its content hash. Multiple file
-- paths can point to the same document (deduplication).
-- ============================================================
CREATE TABLE documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT NOT NULL UNIQUE,            -- SHA-256 of file content
    title           TEXT,                            -- Extracted or LLM-inferred title
    document_type   TEXT NOT NULL,                   -- MIME type (application/pdf, image/png, etc.)
    page_count      INTEGER,
    language        TEXT DEFAULT 'en',               -- ISO 639-1 detected language
    ocr_engine      TEXT,                            -- 'pymupdf_native', 'tesseract', 'ocr_service', 'textract', 'google_vision'
    ocr_confidence  REAL,                            -- 0.0 - 1.0 average confidence across pages
    processing_mode TEXT NOT NULL DEFAULT 'local',   -- 'local' or 'cloud'
    category        TEXT,                            -- LLM-assigned category
    summary         TEXT,                            -- LLM-generated 1-sentence summary
    extracted_date  TEXT,                            -- Date found within document content (ISO 8601)
    status          TEXT NOT NULL DEFAULT 'pending', -- see TaskStatus enum
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    file_size_bytes INTEGER NOT NULL,
    embedding_model TEXT,                            -- Model used for embeddings (for re-index detection)
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    processed_at    TEXT                             -- When processing completed
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_created_at ON documents(created_at);

-- ============================================================
-- File paths: multiple paths can point to the same document.
-- This enables deduplication — when a file is copied or moved,
-- we link the new path to the existing document record instead
-- of reprocessing.
-- ============================================================
CREATE TABLE file_paths (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_path    TEXT NOT NULL UNIQUE,               -- Absolute path on filesystem
    is_primary   INTEGER NOT NULL DEFAULT 1,         -- 1 = canonical path, 0 = duplicate
    first_seen   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_seen    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at   TEXT                                -- Soft-delete when file disappears from disk
);

CREATE INDEX idx_file_paths_document_id ON file_paths(document_id);
CREATE INDEX idx_file_paths_file_path ON file_paths(file_path);
CREATE INDEX idx_file_paths_deleted ON file_paths(deleted_at) WHERE deleted_at IS NOT NULL;

-- ============================================================
-- Document chunks: the extracted text split into retrieval units.
-- Each chunk maps to a vector in ChromaDB via vector_id.
-- Text is stored here (source of truth) AND in ChromaDB
-- (for Chroma's built-in filtering).
-- ============================================================
CREATE TABLE document_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    vector_id    TEXT NOT NULL UNIQUE,               -- UUID, maps to ChromaDB entry
    chunk_index  INTEGER NOT NULL,                   -- Order within document (0-based)
    chunk_text   TEXT NOT NULL,
    page_number  INTEGER,                            -- Source page (1-based, if applicable)
    char_count   INTEGER NOT NULL,                   -- Character count of chunk
    has_embedding INTEGER NOT NULL DEFAULT 0,        -- 1 when embedding stored in ChromaDB
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector_id ON document_chunks(vector_id);
CREATE INDEX idx_chunks_no_embedding ON document_chunks(has_embedding) WHERE has_embedding = 0;

-- ============================================================
-- Tags: many-to-many relationship with documents.
-- Tags can be auto-generated (LLM) or manual (user).
-- ============================================================
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

-- ============================================================
-- Processing log: audit trail of every action taken on a document.
-- Useful for debugging, monitoring, and understanding processing time.
-- ============================================================
CREATE TABLE processing_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    action       TEXT NOT NULL,                       -- 'ingested','ocr_native','ocr_tesseract','ocr_service','ocr_cloud','embedded','classified','error','reprocessed'
    details      TEXT,                                -- JSON blob with action-specific data
    duration_ms  INTEGER,                             -- How long this step took
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_processing_log_document_id ON processing_log(document_id);
CREATE INDEX idx_processing_log_action ON processing_log(action);

-- ============================================================
-- Task queue: persistent, retryable, prioritized task queue.
-- Replaces Redis/arq for simpler NAS deployment.
-- All AI-dependent work flows through this queue.
-- ============================================================
CREATE TABLE task_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type     TEXT NOT NULL,                      -- 'ingest','embed','classify','ocr_cloud','reprocess','file_suggest'
    document_id   INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    priority      INTEGER NOT NULL DEFAULT 5,         -- Higher = more urgent (10=user, 5=watcher, 1=backfill)
    status        TEXT NOT NULL DEFAULT 'pending',    -- 'pending','processing','completed','failed','waiting_llm','cancelled'
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 3,
    payload       TEXT,                               -- JSON: task-specific parameters
    error         TEXT,                               -- Last error message
    scheduled_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    started_at    TEXT,
    completed_at  TEXT,
    next_retry_at TEXT                                -- For exponential backoff
);

CREATE INDEX idx_task_queue_status_priority ON task_queue(status, priority DESC);
CREATE INDEX idx_task_queue_next_retry ON task_queue(next_retry_at) WHERE status = 'waiting_llm';
CREATE INDEX idx_task_queue_document ON task_queue(document_id);

-- ============================================================
-- Filing suggestions: proactive organization recommendations.
-- The organization agent suggests moves; user accepts or rejects.
-- ============================================================
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

-- ============================================================
-- Full-text search on chunk content (works without LLM!)
-- Uses SQLite FTS5 with porter stemming and unicode61 tokenizer.
-- ============================================================
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_text,
    content='document_chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS5 index synchronized with document_chunks
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

-- ============================================================
-- SQLite performance tuning (run at connection time)
-- ============================================================
-- PRAGMA journal_mode = WAL;            -- Write-Ahead Logging for concurrent reads
-- PRAGMA synchronous = NORMAL;          -- Balance durability and speed
-- PRAGMA foreign_keys = ON;             -- Enforce referential integrity
-- PRAGMA busy_timeout = 5000;           -- Wait 5s on lock instead of failing
-- PRAGMA cache_size = -64000;           -- 64MB page cache
-- PRAGMA mmap_size = 268435456;         -- 256MB memory-mapped I/O
```

**Schema differences from prior proposals:**

| Feature | Claude v1 | Reasoner v2 | This Proposal | Rationale |
|---------|-----------|-------------|---------------|-----------|
| `embedding_model` column | No | No | **Yes** | Detect when re-indexing needed after model change |
| `has_embedding` on chunks | No | No | **Yes** | Track which chunks still need embedding (graceful degradation) |
| `char_count` on chunks | `token_count` | `token_count` | **`char_count`** | No tiktoken dep; tokens are model-specific |
| `task_queue` table | No (Redis) | Yes | **Yes** | SQLite-backed queue; zero extra deps |
| `next_retry_at` in queue | No | No | **Yes** | Proper exponential backoff scheduling |
| `filing_suggestions` | Yes | No | **Yes** | Required by PRD Epic 4 |
| `version` on documents | No | Yes | **No** | Over-complicated; re-ingestion creates new document row with new hash |

### 3.2 ChromaDB Collection Schema

```python
import chromadb

def init_vector_store(persist_dir: str) -> chromadb.Collection:
    """Initialize ChromaDB with persistent storage."""
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(
        name="librarian_chunks",
        metadata={
            "hnsw:space": "cosine",       # Cosine similarity
            "hnsw:M": 16,                 # HNSW parameter (default)
            "hnsw:construction_ef": 100,  # Build quality (default)
            "hnsw:search_ef": 50,         # Search quality vs speed
        },
    )
    return collection

# Adding a chunk:
collection.add(
    ids=["chunk-uuid-here"],
    embeddings=[[0.1, 0.2, ...]],         # 768-dim from nomic-embed-text
    documents=["The policy covers..."],    # Stored for Chroma's built-in search
    metadatas=[{
        "document_id": 42,                # FK to SQLite documents.id
        "content_hash": "abc123...",       # For cross-reference
        "page_number": 14,
        "chunk_index": 3,
        "category": "insurance",          # Enables filtered search
        "language": "en",
        "tags": "insurance,legal,auto",   # Comma-separated (Chroma metadata is flat)
        "processing_mode": "local",       # Privacy-aware filtering
    }],
)

# Querying with filters:
results = collection.query(
    query_embeddings=[query_vector],
    n_results=20,
    where={
        "$and": [
            {"processing_mode": {"$eq": "local"}},    # Privacy filter
            {"language": {"$eq": "en"}},               # Language filter
        ]
    },
    include=["documents", "metadatas", "distances"],
)
```

---

## 4. API Surface

### 4.1 REST API (FastAPI)

#### Documents

| Method | Endpoint | Description | Requires LLM |
|--------|----------|-------------|--------------|
| `GET` | `/api/v1/documents` | List documents (paginated, filterable by status/category/tag/path) | No |
| `GET` | `/api/v1/documents/{id}` | Get document details + chunks + file paths | No |
| `POST` | `/api/v1/documents/upload` | Manual file upload (multipart form) | No (queues processing) |
| `DELETE` | `/api/v1/documents/{id}` | Remove from index (soft-delete; file untouched on disk) | No |
| `PATCH` | `/api/v1/documents/{id}` | Update title, tags (manual), category | No |
| `POST` | `/api/v1/documents/{id}/reprocess` | Re-run full pipeline (OCR + embed + classify) | Yes (queued) |

#### Search & Query

| Method | Endpoint | Description | Requires LLM |
|--------|----------|-------------|--------------|
| `GET` | `/api/v1/search/keyword?q=` | FTS5 keyword search | **No** |
| `POST` | `/api/v1/search/semantic` | Vector similarity search | Yes (embedding) |
| `POST` | `/api/v1/search/hybrid` | Fused vector + keyword search (RRF) | Yes (embedding) |
| `POST` | `/api/v1/query` | RAG: natural language question → synthesized answer | Yes (embedding + LLM) |

#### Tags & Organization

| Method | Endpoint | Description | Requires LLM |
|--------|----------|-------------|--------------|
| `GET` | `/api/v1/tags` | List all tags with document counts | No |
| `POST` | `/api/v1/tags` | Create a new tag | No |
| `DELETE` | `/api/v1/tags/{id}` | Delete a tag (unlinks from all documents) | No |
| `GET` | `/api/v1/suggestions` | List pending filing suggestions | No |
| `POST` | `/api/v1/suggestions/{id}/accept` | Accept and execute a filing move | No |
| `POST` | `/api/v1/suggestions/{id}/reject` | Dismiss a suggestion | No |

#### System & Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/status` | Health check: system status, LLM connectivity, queue depth, storage stats |
| `GET` | `/api/v1/queue` | Task queue overview (pending/processing/failed counts by type) |
| `POST` | `/api/v1/queue/pause` | Pause all background processing |
| `POST` | `/api/v1/queue/resume` | Resume background processing |
| `GET` | `/api/v1/config` | Current config (secrets redacted) |
| `PUT` | `/api/v1/config` | Update runtime config (LLM endpoint, OCR settings, etc.) |
| `POST` | `/api/v1/reindex` | Trigger re-embedding of all documents (e.g., after model change) |

### 4.2 WebSocket API

```
WS /api/v1/ws
```

Real-time event stream for UI updates. Single WebSocket connection per client, multiplexed event types:

```python
# Event schema
class WSEvent(BaseModel):
    event: str          # Dotted event name
    data: dict          # Event-specific payload
    timestamp: str      # ISO 8601

# --- System events ---
{"event": "system.llm.connected",    "data": {"provider": "ollama", "model": "llama3.2"}}
{"event": "system.llm.disconnected", "data": {"reason": "connection_refused"}}
{"event": "system.queue.stats",      "data": {"pending": 12, "processing": 3, "waiting_llm": 5, "failed": 1}}

# --- Document lifecycle events ---
{"event": "document.discovered", "data": {"path": "/mnt/nas/new.pdf", "size_bytes": 245000}}
{"event": "document.duplicate",  "data": {"path": "/mnt/nas/copy.pdf", "existing_id": 42}}
{"event": "document.processing", "data": {"id": 42, "step": "ocr", "page": 3, "total_pages": 10}}
{"event": "document.completed",  "data": {"id": 42, "title": "Insurance Policy", "category": "insurance"}}
{"event": "document.error",      "data": {"id": 42, "error": "OCR timeout", "retryable": true}}

# --- Classification events ---
{"event": "classification.completed", "data": {"id": 42, "category": "tax", "tags": ["2024", "w2"]}}

# --- Filing suggestion events ---
{"event": "suggestion.created", "data": {"id": 7, "doc_id": 42, "from": "/inbox/doc.pdf", "to": "/taxes/2024/w2.pdf"}}
```

**Implementation:**

```python
from fastapi import WebSocket
import asyncio

class WebSocketManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, event: str, data: dict):
        """Send event to all connected clients. Remove dead connections."""
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)
```

### 4.3 Key Request/Response Schemas

```python
from pydantic import BaseModel, Field

# --- Search ---

class KeywordSearchParams(BaseModel):
    q: str                                # Search query
    page: int = 1
    per_page: int = 50
    filter_tags: list[str] | None = None
    filter_category: str | None = None

class SemanticSearchRequest(BaseModel):
    query: str                            # Natural language query
    top_k: int = Field(20, ge=1, le=100)
    filter_tags: list[str] | None = None
    filter_category: str | None = None
    threshold: float = Field(0.3, ge=0.0, le=1.0)

class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = Field(20, ge=1, le=100)
    filter_tags: list[str] | None = None
    filter_category: str | None = None
    vector_weight: float = Field(1.0, ge=0.0, le=5.0)
    keyword_weight: float = Field(1.0, ge=0.0, le=5.0)

class SearchResult(BaseModel):
    document_id: int
    title: str | None
    file_path: str                        # Primary file path
    page_number: int | None
    chunk_text: str                       # Relevant excerpt
    score: float                          # Similarity or RRF score
    tags: list[str]
    category: str | None

class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    search_time_ms: int
    search_mode: str                      # 'keyword', 'semantic', 'hybrid'
    degraded: bool = False                # True if semantic unavailable

# --- RAG Query ---

class QueryRequest(BaseModel):
    query: str                            # Natural language question
    top_k: int = Field(10, ge=1, le=50)   # Chunks to retrieve for context
    filter_tags: list[str] | None = None
    filter_category: str | None = None
    include_sources: bool = True

class Source(BaseModel):
    document_id: int
    title: str | None
    file_path: str
    page_number: int | None
    chunk_text: str
    similarity: float

class QueryResponse(BaseModel):
    answer: str                           # LLM-synthesized answer
    sources: list[Source]                  # Supporting evidence
    confidence: float                     # Average retrieval similarity
    query_time_ms: int
    model_used: str                       # Which LLM produced the answer

# --- Documents ---

class DocumentListParams(BaseModel):
    page: int = 1
    per_page: int = Field(50, ge=1, le=200)
    status: str | None = None             # Filter by processing status
    category: str | None = None
    tag: str | None = None
    q: str | None = None                  # FTS5 search filter
    sort_by: str = "created_at"           # created_at, title, file_size_bytes, updated_at
    sort_order: str = "desc"              # asc, desc

class DocumentDetail(BaseModel):
    id: int
    content_hash: str
    title: str | None
    document_type: str
    page_count: int | None
    language: str
    ocr_engine: str | None
    ocr_confidence: float | None
    category: str | None
    summary: str | None
    status: str
    file_size_bytes: int
    tags: list[str]
    file_paths: list[str]
    created_at: str
    processed_at: str | None

# --- Status ---

class SystemStatus(BaseModel):
    version: str
    uptime_seconds: int
    llm_connected: bool
    llm_provider: str | None
    llm_model: str | None
    embedding_connected: bool
    embedding_model: str | None
    queue: QueueStatus
    storage: StorageStatus

class QueueStatus(BaseModel):
    pending: int
    processing: int
    waiting_llm: int
    failed: int
    completed_today: int

class StorageStatus(BaseModel):
    total_documents: int
    total_chunks: int
    total_embeddings: int                 # Chunks with has_embedding=1
    sqlite_size_mb: float
    chromadb_size_mb: float
```

---

## 5. Key Architectural Decisions

### 5.1 Single Process, Async Workers with ProcessPoolExecutor Escape Hatch

**Decision:** Run the entire application in one Python process using `asyncio`. Use `ProcessPoolExecutor` for CPU-bound OCR only.

```
Main Process (uvicorn)
 ├── FastAPI HTTP handlers          (async coroutines)
 ├── WebSocket manager              (async coroutines)
 ├── File watcher                   (watchdog thread → asyncio queue bridge)
 ├── Queue workers (N=2-4)          (async coroutines consuming from SQLite queue)
 │   └── OCR step                   (offloaded to ProcessPoolExecutor)
 └── Background scheduler           (periodic health checks, cleanup, backfill)
```

**Trade-offs:**

| Pro | Con |
|-----|-----|
| Minimal RAM (one process ~200MB base) | CPU-bound OCR can starve event loop |
| Simple deployment (one container) | Single point of failure |
| Shared in-memory caches | GIL limits CPU parallelism |
| No IPC overhead | Harder to scale horizontally |

**Mitigation for CPU-bound OCR:**

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

# Module-level pool (reused across workers)
_ocr_pool = ProcessPoolExecutor(max_workers=2)

async def run_ocr_in_process(image_bytes: bytes, lang: str) -> str:
    """Run Tesseract in a separate process to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_ocr_pool, _tesseract_sync, image_bytes, lang)

def _tesseract_sync(image_bytes: bytes, lang: str) -> str:
    """Synchronous Tesseract call (runs in subprocess)."""
    from PIL import Image
    import pytesseract
    import io
    image = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(image, lang=lang)
```

### 5.2 Content-Addressed Storage with Two-Phase Hashing

**Decision:** Documents identified by SHA-256 content hash. File paths are a separate table with N:1 relationship to documents.

**What this enables:**
- File copy → link new path, no reprocessing
- File move → update path, no reprocessing
- File rename → update path, no reprocessing
- Same file in multiple folders → one document, many paths
- File updated (same path, new content) → new document, old document soft-deleted

**Two-phase hashing on startup:**

```python
async def startup_scan(watched_dirs: list[str], db: Database):
    """Reconcile filesystem state with database on startup."""
    known_fingerprints = await db.get_all_fingerprints()  # {quick_fp: doc_id}

    for directory in watched_dirs:
        for path in walk_supported_files(directory):
            fp = quick_fingerprint(path)

            if fp in known_fingerprints:
                # Known file — update last_seen timestamp
                await db.touch_file_path(path)
                continue

            # Potentially new file — compute full hash
            full_hash = canonical_hash(path)
            existing = await db.get_document_by_hash(full_hash)

            if existing:
                # Same content, new path (file was copied/moved)
                await db.add_file_path(existing.id, path, is_primary=False)
            else:
                # Genuinely new file — queue for processing
                await queue.enqueue("ingest", path=path, priority=1)  # Low priority (backfill)
```

### 5.3 Externalized OCR (Mirrors LLM Pattern)

**Decision:** Tesseract is built-in (no ML deps). Users who want better OCR can configure an external OCR service endpoint, just like they configure an external LLM endpoint.

**Rationale:** This follows the constraint's spirit — "externalize all AI" — and gives users PaddleOCR/Surya accuracy without violating constraints. The application itself carries zero ML framework dependencies.

```yaml
# config.yaml
ocr:
  primary: tesseract                    # Built-in, always available
  tesseract_lang: eng+fra              # Tesseract language packs
  service:
    url: null                           # External OCR service (optional)
    # Example: http://192.168.1.100:8080/ocr
    # Users can run PaddleOCR, Surya, EasyOCR as a container
    timeout: 30
  cloud:
    provider: null                      # aws_textract, google_vision (optional)
    region: us-east-1
  confidence_threshold: 0.7            # Below this, try next OCR option
```

### 5.4 SQLite-Backed Task Queue

**Decision:** Use a `task_queue` table in SQLite instead of Redis/arq.

**Rationale:** For a single-user NAS system, Redis adds operational complexity (another container, monitoring, config) without meaningful benefit. The SQLite queue gives us:
- **Persistence**: survives restarts (same DB file)
- **Prioritization**: ORDER BY priority DESC, scheduled_at ASC
- **Retryability**: attempts < max_attempts, exponential backoff via next_retry_at
- **Visibility**: query the queue with SQL for status/monitoring
- **Atomicity**: ACID transactions for state changes

```python
class TaskQueue:
    """SQLite-backed persistent task queue with priority and retry support."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue(
        self,
        task_type: str,
        document_id: int | None = None,
        priority: int = 5,
        payload: dict | None = None,
    ) -> int:
        """Add a task to the queue. Returns task ID."""
        result = await self.db.execute(
            text("""
                INSERT INTO task_queue (task_type, document_id, priority, payload)
                VALUES (:type, :doc_id, :priority, :payload)
            """),
            {"type": task_type, "doc_id": document_id, "priority": priority,
             "payload": json.dumps(payload) if payload else None},
        )
        await self.db.commit()
        return result.lastrowid

    async def dequeue(self, task_types: list[str] | None = None) -> dict | None:
        """Claim the highest-priority pending task. Returns None if queue empty."""
        type_filter = ""
        params = {"now": datetime.utcnow().isoformat() + "Z"}
        if task_types:
            placeholders = ",".join(f":t{i}" for i in range(len(task_types)))
            type_filter = f"AND task_type IN ({placeholders})"
            params.update({f"t{i}": t for i, t in enumerate(task_types)})

        result = await self.db.execute(
            text(f"""
                UPDATE task_queue
                SET status = 'processing', started_at = :now, attempts = attempts + 1
                WHERE id = (
                    SELECT id FROM task_queue
                    WHERE status IN ('pending', 'waiting_llm')
                    AND (next_retry_at IS NULL OR next_retry_at <= :now)
                    {type_filter}
                    ORDER BY priority DESC, scheduled_at ASC
                    LIMIT 1
                )
                RETURNING *
            """),
            params,
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def complete(self, task_id: int, result: dict | None = None):
        """Mark a task as completed."""
        await self.db.execute(
            text("""
                UPDATE task_queue
                SET status = 'completed', completed_at = :now, result = :result
                WHERE id = :id
            """),
            {"id": task_id, "now": datetime.utcnow().isoformat() + "Z",
             "result": json.dumps(result) if result else None},
        )
        await self.db.commit()

    async def fail(self, task_id: int, error: str):
        """Mark a task as failed. Schedule retry with exponential backoff if attempts remain."""
        task = await self.get(task_id)
        if task["attempts"] >= task["max_attempts"]:
            new_status = "failed"
            next_retry = None
        else:
            new_status = "waiting_llm"
            delay = min(300, 5 * (2 ** task["attempts"]))  # 5s, 10s, 20s, ... max 5min
            next_retry = (datetime.utcnow() + timedelta(seconds=delay)).isoformat() + "Z"

        await self.db.execute(
            text("""
                UPDATE task_queue
                SET status = :status, error = :error, next_retry_at = :retry
                WHERE id = :id
            """),
            {"id": task_id, "status": new_status, "error": error, "retry": next_retry},
        )
        await self.db.commit()
```

**Upgrade path to Redis:** If the system grows beyond single-NAS (multi-worker, distributed), swap `TaskQueue` implementation to use `arq` + Redis. The interface is the same — only the backend changes.

### 5.5 Hybrid Search with Reciprocal Rank Fusion

**Decision:** Support three search modes: keyword (FTS5), semantic (ChromaDB), and hybrid (RRF fusion of both).

**Why this matters:**
- "Find invoice #INV-2024-0137" → keyword search wins (exact match)
- "Documents about retirement planning" → semantic search wins (conceptual)
- "What did the doctor say about my blood pressure?" → hybrid wins (specific terms + context)

FTS5 keyword search **always works**, even without LLM. This is the graceful degradation path.

### 5.6 Graceful Degradation Model

**Decision:** The system functions at three levels depending on LLM availability.

| Capability | Full Mode (LLM up) | Degraded Mode (LLM down) | Offline Mode (no network) |
|------------|--------------------|-----------------------|--------------------------|
| File watching & ingestion | Full pipeline | Text extraction only; AI tasks queued | Text extraction only |
| OCR (Tesseract built-in) | Works | Works | Works |
| OCR (external service) | Works | Depends on service | No |
| Text extraction (PyMuPDF) | Works | Works | Works |
| Keyword search (FTS5) | Works | Works | Works |
| Semantic search (vectors) | Works | **No** (can't embed query) | No |
| RAG Q&A | Works | **No** (needs LLM) | No |
| Auto-classification | Works | **Queued** | Queued |
| Auto-tagging | Works | **Queued** | Queued |
| Manual tagging | Works | Works | Works |
| Filing suggestions | Works | **Queued** | Queued |
| Document browsing | Works | Works | Works |

**LLM health monitoring:**

```python
class LLMHealthMonitor:
    """Periodic health check for LLM and embedding services."""

    def __init__(self, llm_client, embed_client, ws_manager, check_interval: int = 30):
        self.llm = llm_client
        self.embed = embed_client
        self.ws = ws_manager
        self.interval = check_interval
        self.llm_available = False
        self.embed_available = False

    async def run(self):
        """Background task: check LLM/embedding health every N seconds."""
        while True:
            llm_ok = await self.llm.health_check()
            embed_ok = await self.embed.health_check()

            if llm_ok != self.llm_available:
                self.llm_available = llm_ok
                event = "system.llm.connected" if llm_ok else "system.llm.disconnected"
                await self.ws.broadcast(event, {"provider": self.llm.config.provider})

                if llm_ok:
                    # LLM came back online — resume queued tasks
                    await self._resume_waiting_tasks()

            if embed_ok != self.embed_available:
                self.embed_available = embed_ok
                event = "system.embedding.connected" if embed_ok else "system.embedding.disconnected"
                await self.ws.broadcast(event, {"model": self.embed.config.model})

            await asyncio.sleep(self.interval)

    async def _resume_waiting_tasks(self):
        """Move waiting_llm tasks back to pending for processing."""
        await self.db.execute(
            text("UPDATE task_queue SET status = 'pending' WHERE status = 'waiting_llm'")
        )
        await self.db.commit()
```

### 5.7 Embedding Model Tracking for Re-indexing

**Decision:** Store the embedding model name on each document. When the configured model changes, detect stale embeddings and offer re-indexing.

**Why this matters:** If a user switches from `nomic-embed-text` to `bge-small-en`, all existing vectors are incompatible with new query embeddings. The system must detect this and re-embed.

```python
async def check_embedding_model_change(config, db):
    """Detect if the configured embedding model differs from what's stored."""
    current_model = config.ai.embedding.model
    stale_count = await db.scalar(
        text("""
            SELECT COUNT(*) FROM documents
            WHERE embedding_model IS NOT NULL
            AND embedding_model != :model
            AND status = 'completed'
        """),
        {"model": current_model},
    )
    if stale_count > 0:
        logger.warning(
            f"Embedding model changed to {current_model}. "
            f"{stale_count} documents have stale embeddings. "
            f"Run POST /api/v1/reindex to update."
        )
    return stale_count
```

---

## 6. Bottlenecks & Mitigations

### 6.1 OCR Throughput

**Impact:** Tesseract processes ~1-3 pages/second on NAS-class CPU. 50K docs × avg 5 pages × 40% needing OCR = 100K pages = 9-28 hours.

| Mitigation | Effect |
|------------|--------|
| PyMuPDF native extraction first | Eliminates OCR for ~60% of PDFs (born-digital) |
| ProcessPoolExecutor (2 workers) | Parallel OCR without blocking event loop |
| External OCR service | Offload to GPU machine (PaddleOCR in Docker) |
| Priority queue | New files processed first; backfill runs during idle |
| Incremental backfill with throttling | Process 50 docs, sleep 30s (prevents NAS thermal throttle) |
| Cloud OCR for difficult pages | Textract/Google Vision for low-confidence results |

### 6.2 Embedding Generation

**Impact:** Ollama embedding calls ~50-100ms per chunk over HTTP. 50K docs × 10 chunks = 500K chunks = 7-14 hours.

| Mitigation | Effect |
|------------|--------|
| Batch embedding (32 chunks/request) | Reduces HTTP overhead by 32x |
| Pipeline parallelism | Embed batch N while extracting text from batch N+1 |
| Skip re-embedding | `has_embedding` flag prevents redundant work |
| Defer embedding | Documents searchable by keyword immediately; vectors added async |

### 6.3 Memory Constraints (16GB NAS)

**Budget breakdown for NAS with 16GB RAM:**

| Component | RAM Usage | Notes |
|-----------|-----------|-------|
| Synology DSM + services | ~3-4 GB | OS, Plex, Docker daemon, etc. |
| Librarian app (Python) | ~200 MB | FastAPI + SQLite + workers |
| ChromaDB (embedded) | ~300-800 MB | Depends on collection size; uses mmap |
| Tesseract (per page) | ~100 MB | Transient; per OCR call |
| **Available for other containers** | **~10-12 GB** | Ollama, PaddleOCR service, etc. |

**Key insight:** Librarian itself is lightweight (~500MB). The heavy component (Ollama) is external — it can run on a separate machine with a GPU, consuming zero NAS RAM.

| Mitigation | Effect |
|------------|--------|
| Externalized LLM (Ollama on GPU server) | Zero LLM RAM on NAS |
| ChromaDB mmap (`persist_directory` on SSD) | OS manages page cache; doesn't pin in RAM |
| Streaming page-by-page OCR | Never load entire PDF in memory |
| Configurable `max_file_size_mb` | Skip very large files with warning |

### 6.4 SQLite Write Contention

**Impact:** SQLite allows one writer at a time. Under heavy ingestion, writes can queue up.

| Mitigation | Effect |
|------------|--------|
| WAL mode (`PRAGMA journal_mode=WAL`) | Concurrent reads during writes |
| Batch writes (buffer 50 rows, flush every 5s) | Fewer write transactions |
| Separate read/write connections | Read queries never blocked by writes |
| `busy_timeout=5000` | Wait 5 seconds instead of immediate SQLITE_BUSY error |

**Real-world impact:** At ~10 documents/minute ingestion rate (realistic for NAS), SQLite handles this trivially. Write contention only matters at >100 writes/second sustained, which this system will never hit.

### 6.5 ChromaDB at Scale (500K+ Vectors)

**Impact:** HNSW index rebuild on startup can take minutes with 500K vectors. Query latency may increase.

| Mitigation | Effect |
|------------|--------|
| Metadata filtering (`where` clause) | Narrows search space before vector comparison |
| Persist directory on SSD (not HDD) | Faster mmap access |
| Tuned HNSW params (`search_ef=50`) | Balance quality vs. speed |
| Future: pgvector upgrade path | For archives > 100K documents |

### 6.6 File System Watching at Scale

**Impact:** `watchdog` on very large directories (50K+ files, deep nesting) can be slow on network drives.

| Mitigation | Effect |
|------------|--------|
| Debouncing (2-second window) | Groups rapid file system events |
| Ignore patterns (`.tmp`, `.swp`, `.*`) | Reduces noise |
| Polling fallback for NFS/SMB | Network drives often don't support inotify |
| Startup reconciliation scan | Detect changes that happened while service was stopped |

---

## 7. Missing PRD Features

### 7.1 Critical Gaps (Must Address in v1)

**1. Document Versioning / Change Detection**

The PRD handles dedup (same content, different path) but not updates (same path, different content). When `contract.pdf` is overwritten with new content:

- Watcher detects modification event
- New SHA-256 hash computed → differs from stored hash
- Create new document record with new hash
- Mark old document's file_path as superseded
- Old document remains searchable (old chunks, old vectors)
- New document queued for full processing

**Schema addition:**
```sql
ALTER TABLE file_paths ADD COLUMN superseded_by INTEGER REFERENCES documents(id);
```

**2. Error Recovery & Retry Strategy**

The task queue implements exponential backoff: 5s → 10s → 20s → 40s → ... → max 5 minutes. After `max_attempts` (default 3), task moves to `failed` status.

Error categories:
- **Transient** (retry): network timeout, Ollama busy, temporary disk full
- **Permanent** (fail): unsupported file format, corrupted PDF, invalid encoding
- **Dependency** (wait): LLM unavailable → status `waiting_llm`, auto-resume on reconnect

Dead letter inspection: `GET /api/v1/queue?status=failed` returns failed tasks with error messages for manual review.

**3. Backup & Restore**

SQLite and ChromaDB must be backed up atomically:

```python
async def backup(backup_dir: str):
    """Atomic backup of SQLite + ChromaDB."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = Path(backup_dir) / timestamp

    # 1. SQLite online backup (consistent snapshot)
    src_db = sqlite3.connect(config.storage.sqlite_path)
    dst_db = sqlite3.connect(str(dest / "librarian.db"))
    src_db.backup(dst_db)
    dst_db.close()
    src_db.close()

    # 2. ChromaDB: copy persist directory (pause writes first)
    shutil.copytree(config.storage.chromadb_path, dest / "chromadb")

    # 3. Record backup metadata
    (dest / "backup.json").write_text(json.dumps({
        "timestamp": timestamp,
        "documents": total_docs,
        "chunks": total_chunks,
        "embedding_model": config.ai.embedding.model,
    }))
```

**Recovery from corrupted ChromaDB:** Since all chunk text is stored in SQLite, ChromaDB can be rebuilt:
```
POST /api/v1/reindex    → Re-embed all chunks from SQLite into ChromaDB
```

**4. File Deletion Handling**

When a watched file is deleted from disk:
- Watcher detects deletion event
- Soft-delete the `file_path` record (`deleted_at = now`)
- If document has other non-deleted paths → document remains fully active
- If document has no remaining paths → document becomes "orphaned"
- Orphaned documents remain searchable but flagged in UI
- Configurable auto-purge: remove orphaned documents after N days

**5. Monitoring & Observability**

```python
# GET /api/v1/status returns comprehensive health:
{
    "version": "0.1.0",
    "uptime_seconds": 86400,
    "llm": {"connected": true, "provider": "ollama", "model": "llama3.2", "latency_ms": 45},
    "embedding": {"connected": true, "model": "nomic-embed-text", "latency_ms": 12},
    "ocr_service": {"configured": false},
    "queue": {"pending": 3, "processing": 1, "waiting_llm": 0, "failed": 0, "completed_today": 47},
    "storage": {
        "documents": 12450, "chunks": 98340, "embeddings": 98340,
        "sqlite_mb": 156.3, "chromadb_mb": 892.1, "disk_free_gb": 45.2
    },
    "processing_rate": {"docs_per_hour": 120, "avg_ocr_ms": 2400, "avg_embed_ms": 85}
}
```

### 7.2 Important Gaps (v2 Features)

**6. Multi-Language OCR:** Route to correct Tesseract language pack based on `langdetect` output. Support `eng+fra+deu` multi-language mode.

**7. Structured Data Extraction:** Use LLM to extract key-value pairs (invoice numbers, totals, dates) from classified documents. Store in a `document_properties` table.

**8. Access Control:** API key authentication (`X-API-Key` header). Single-user initially; per-user visibility for multi-user deployments.

**9. Document Preview:** Generate thumbnails via PyMuPDF's `page.get_pixmap()`. Serve via `GET /api/v1/documents/{id}/thumbnail`.

**10. Incremental Re-indexing:** `POST /api/v1/reindex` with options: `{"scope": "all" | "model_changed" | "failed_only"}`.

### 7.3 Future Features (v3+)

- Document relationships and cross-references
- Calendar integration (extract dates, push reminders)
- Email/IMAP ingestion
- Webhook notifications
- Export to CSV/PDF
- OCR correction feedback loop
- Retention policies
- Mobile-responsive web UI

---

## 8. Configuration

```yaml
# config.yaml — full configuration with defaults and environment variable support

# ============================================================
# File watching
# ============================================================
watcher:
  directories:
    - /mnt/nas/documents
    - /mnt/nas/scans
  supported_extensions:
    - .pdf
    - .png
    - .jpg
    - .jpeg
    - .tiff
    - .tif
    - .bmp
    - .webp
  ignore_patterns:
    - "*.tmp"
    - "*.swp"
    - "*.partial"
    - ".*"                              # Hidden files
    - "@eaDir/*"                        # Synology metadata
    - "#recycle/*"                      # Synology recycle bin
  debounce_ms: 2000
  polling_interval_sec: 60             # Fallback for network drives

# ============================================================
# Document processing
# ============================================================
processing:
  max_file_size_mb: 100
  max_concurrent_workers: 2            # Async workers for ingestion
  ocr:
    primary: tesseract                  # Built-in, no ML deps
    tesseract_lang: eng                 # Tesseract language packs (eng+fra+deu)
    service:
      url: ${OCR_SERVICE_URL:}          # External OCR service (optional)
      timeout: 30
    cloud:
      provider: ${OCR_CLOUD_PROVIDER:}  # aws_textract, google_vision
      region: ${AWS_REGION:us-east-1}
    confidence_threshold: 0.7           # Below this, try next OCR method
  chunking:
    max_chars: 1500                     # ~375 tokens at 4 chars/token
    overlap_chars: 200                  # ~50 tokens overlap

# ============================================================
# AI / LLM configuration
# ============================================================
ai:
  llm:
    provider: ollama
    base_url: ${OLLAMA_HOST:http://localhost:11434}
    model: ${LLM_MODEL:llama3.2:latest}
    timeout: 120
    max_retries: 3
  embedding:
    provider: ollama
    base_url: ${OLLAMA_HOST:http://localhost:11434}
    model: ${EMBEDDING_MODEL:nomic-embed-text:latest}
    batch_size: 32
  classification:
    enabled: true
    model: ${CLASSIFICATION_MODEL:llama3.2:1b}  # Smaller model for classification
    sample_chunks: 2                              # First N chunks sent to LLM

# ============================================================
# Privacy controls
# ============================================================
privacy:
  default_mode: local                   # 'local' or 'cloud'
  sensitive_paths:                      # Force local processing for these paths
    - /mnt/nas/financial
    - /mnt/nas/medical
    - /mnt/nas/legal
  cloud_require_approval: true          # Require explicit approval for cloud OCR

# ============================================================
# Storage
# ============================================================
storage:
  sqlite_path: ${LIBRARIAN_DB:/var/lib/librarian/librarian.db}
  chromadb_path: ${LIBRARIAN_CHROMADB:/var/lib/librarian/chromadb}
  backup:
    enabled: true
    directory: ${LIBRARIAN_BACKUP:/var/lib/librarian/backups}
    interval_hours: 24
    keep_count: 7                       # Number of backups to retain

# ============================================================
# Task queue
# ============================================================
queue:
  max_retries: 3
  retry_base_delay_sec: 5               # Exponential backoff: 5, 10, 20, 40, ...
  retry_max_delay_sec: 300              # Cap at 5 minutes
  health_check_interval_sec: 30         # LLM health check frequency
  backfill:
    batch_size: 50                      # Documents per batch
    pause_between_batches_sec: 30       # Prevent thermal throttling

# ============================================================
# API server
# ============================================================
server:
  host: ${HOST:0.0.0.0}
  port: ${PORT:8000}
  cors_origins:
    - "http://localhost:3000"
    - "http://localhost:5173"
  auth:
    enabled: false
    api_key: ${API_KEY:}
```

---

## 9. Project Structure

```
librarian/
├── pyproject.toml                      # Project metadata, dependencies, build config
├── alembic.ini                         # Alembic migration config
├── alembic/
│   ├── env.py
│   └── versions/                       # Migration scripts
├── config/
│   └── config.example.yaml             # Example configuration
├── src/
│   └── librarian/
│       ├── __init__.py                 # Package init, version
│       ├── __main__.py                 # Entry point: python -m librarian
│       ├── config.py                   # Pydantic Settings model (YAML + env vars)
│       ├── app.py                      # FastAPI app factory, lifespan events
│       │
│       ├── api/                        # HTTP API layer
│       │   ├── __init__.py
│       │   ├── router.py              # Main router aggregating sub-routers
│       │   ├── documents.py           # Document CRUD endpoints
│       │   ├── search.py              # Search & query endpoints
│       │   ├── tags.py                # Tag management endpoints
│       │   ├── suggestions.py         # Filing suggestion endpoints
│       │   ├── system.py              # Health, status, config endpoints
│       │   └── websocket.py           # WebSocket event stream
│       │
│       ├── core/                       # Core application logic
│       │   ├── __init__.py
│       │   ├── watcher.py             # File system watcher (watchdog integration)
│       │   ├── queue.py               # SQLite-backed task queue
│       │   ├── worker.py              # Async worker pool (consumes from queue)
│       │   ├── scheduler.py           # Background tasks (health checks, cleanup, backfill)
│       │   └── events.py             # WebSocket event manager
│       │
│       ├── processing/                 # Document processing pipeline
│       │   ├── __init__.py
│       │   ├── hasher.py              # Two-phase hashing (xxhash + SHA-256)
│       │   ├── extractor.py           # PyMuPDF native text extraction
│       │   ├── ocr.py                 # OCR router (Tesseract / service / cloud)
│       │   ├── chunker.py             # Text chunking (custom, ~80 LOC)
│       │   └── pipeline.py            # Orchestrates full ingestion pipeline
│       │
│       ├── intelligence/               # AI/LLM integration (all via HTTP)
│       │   ├── __init__.py
│       │   ├── embedder.py            # Embedding via Ollama/LiteLLM
│       │   ├── classifier.py          # Document classification via LLM
│       │   ├── query_engine.py        # RAG query pipeline
│       │   ├── suggester.py           # Filing suggestion agent
│       │   └── prompts/               # Jinja2 prompt templates
│       │       ├── classify.j2
│       │       ├── query.j2
│       │       ├── summarize.j2
│       │       └── file_suggest.j2
│       │
│       └── storage/                    # Data access layer
│           ├── __init__.py
│           ├── database.py            # SQLAlchemy engine, session factory, pragmas
│           ├── models.py              # SQLAlchemy ORM models
│           ├── vector_store.py        # ChromaDB wrapper
│           └── repositories.py        # Data access patterns (queries, batch ops)
│
├── tests/
│   ├── conftest.py                    # Shared fixtures (temp DB, test config)
│   ├── test_hasher.py
│   ├── test_extractor.py
│   ├── test_chunker.py
│   ├── test_ocr.py
│   ├── test_queue.py
│   ├── test_search.py
│   ├── test_api/
│   │   ├── test_documents.py
│   │   ├── test_search.py
│   │   └── test_system.py
│   └── fixtures/
│       ├── sample_digital.pdf          # Born-digital PDF (has embedded text)
│       ├── sample_scanned.pdf          # Scanned PDF (needs OCR)
│       └── sample_image.png            # Image file
│
├── docker/
│   ├── Dockerfile                      # Multi-stage build (slim Python image)
│   ├── docker-compose.yml              # Librarian + Ollama
│   └── docker-compose.full.yml         # Librarian + Ollama + PaddleOCR service
│
└── docs/
    ├── PRD.md
    ├── ARCHITECTURE-CONSTRAINTS.md
    └── architecture-v2-claude.md       # This document
```

**Key structural differences from prior proposals:**

| Change | Rationale |
|--------|-----------|
| `intelligence/` instead of `llm/` | Clearer: this package handles all AI (embeddings, classification, RAG), not just LLM |
| `processing/pipeline.py` | Orchestrator that ties hasher → extractor → OCR → chunker together |
| `core/events.py` | Separate WebSocket event manager from API layer |
| `api/tags.py` | Tags deserve their own router (CRUD operations) |
| No `llm/agents.py` | "Agents" are just functions in `classifier.py`, `query_engine.py`, `suggester.py` |

---

## 10. Implementation Milestones

Reordered for fastest time-to-value. Each milestone produces a usable increment.

| Phase | Deliverable | Key Outcome | LLM Required? |
|-------|-------------|-------------|----------------|
| **M1** | Project skeleton + config + CLI + SQLite schema + Alembic | `librarian init`, `librarian config show` | No |
| **M2** | File watcher + two-phase dedup + task queue | Files detected, deduped, queued | No |
| **M3** | PyMuPDF text extraction + chunking + FTS5 | **Keyword search works** (no AI needed!) | **No** |
| **M4** | REST API (document CRUD + keyword search) | **Users can browse and search** | No |
| **M5** | Tesseract OCR for scanned documents | Scanned PDFs become searchable | No |
| **M6** | Ollama embeddings + ChromaDB + semantic search | **Semantic search available** | Yes |
| **M7** | RAG query interface (LiteLLM) | Natural language Q&A | Yes |
| **M8** | Auto-classification + tagging | Documents auto-categorized | Yes |
| **M9** | Filing suggestions + organization agent | Proactive file organization | Yes |
| **M10** | WebSocket events + real-time status | Live UI updates | No |
| **M11** | External OCR service support | PaddleOCR accuracy via HTTP | No |
| **M12** | Cloud OCR fallback + privacy controls | AWS Textract / Google Vision | No |
| **M13** | Backup/restore + monitoring + health checks | Production-ready operations | No |
| **M14** | Docker compose + deployment docs | One-command deployment | No |

**Key insight from the Reasoner (adopted here):** By moving PyMuPDF extraction and FTS5 keyword search to M3 (before OCR and AI), users get a working searchable archive with zero AI dependencies. This makes the product useful at M4 — long before Ollama, embeddings, or LLM are configured. Progressive enhancement adds capabilities as AI services become available.

---

## 11. Docker Deployment

```yaml
# docker-compose.yml — minimal deployment
version: "3.8"

services:
  librarian:
    build: ./docker
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - librarian-data:/var/lib/librarian
      - /mnt/nas/documents:/mnt/nas/documents:ro  # Watch directory (read-only)
    environment:
      - OLLAMA_HOST=http://ollama:11434
      - LIBRARIAN_DB=/var/lib/librarian/librarian.db
      - LIBRARIAN_CHROMADB=/var/lib/librarian/chromadb
    depends_on:
      - ollama
    restart: unless-stopped
    mem_limit: 1g  # Librarian itself is lightweight

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    # For GPU support, uncomment:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - capabilities: [gpu]
    restart: unless-stopped

volumes:
  librarian-data:
  ollama-models:
```

```yaml
# docker-compose.full.yml — with external OCR service
version: "3.8"

services:
  librarian:
    # ... same as above, plus:
    environment:
      - OCR_SERVICE_URL=http://ocr:8080/ocr

  ollama:
    # ... same as above

  ocr:
    image: paddleocr-server:latest  # Custom or community PaddleOCR HTTP wrapper
    ports:
      - "8080:8080"
    restart: unless-stopped
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - capabilities: [gpu]

volumes:
  librarian-data:
  ollama-models:
```

---

## 12. Summary: Why This Proposal

This architecture synthesizes the best ideas from all prior proposals while strictly adhering to constraints:

| Principle | Implementation |
|-----------|----------------|
| **No in-process AI** | All embeddings/LLM via HTTP (LiteLLM + httpx). Zero ML framework deps. |
| **Externalize everything heavy** | LLM → Ollama. OCR → optional service. App is ~500MB RAM. |
| **Graceful degradation** | Keyword search always works. AI features queue when offline. |
| **Progressive value** | Useful at M4 (keyword search). AI enhances, never blocks. |
| **NAS-practical** | Single process, ~500MB RAM, SQLite queue, no Redis required. |
| **Production-ready** | Backup/restore, health monitoring, retry logic, audit trail. |
| **Maintainable** | ~200 LOC for LLM layer. No LangChain/LlamaIndex. Jinja2 templates. |
| **Extensible** | OCR service endpoint. LiteLLM provider switching. pgvector upgrade path. |

The architecture enables a document intelligence platform that starts simple (file watching + keyword search) and progressively enhances with AI capabilities — without ever requiring AI to function.
