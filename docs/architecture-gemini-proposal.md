# Architecture Proposal: Gemini Analysis

**Source:** Gemini CLI
**Date:** 2026-02-15

---

## 1. Recommended Python Libraries

| Component | Library | Rationale |
|-----------|---------|-----------|
| **File System Watcher** | `watchdog` | Industry-standard, cross-platform, reliable, lightweight |
| **Document Parsing & OCR** | `unstructured` | Abstracts complexity of parsing different document types; intelligent partitioning; integrates with various OCR engines |
| **Underlying OCR Engine** | `paddleocr` (via `unstructured`) | Superior accuracy over Tesseract for varied layouts and scanned documents |
| **Embedding Model** | `sentence-transformers` with `all-MiniLM-L6-v2` | Excellent balance of performance and size (80MB); fast; small memory footprint |
| **Vector Database** | `chromadb` | Modern, open-source; runs in-process or standalone; persists to disk; seamless integration |
| **Metadata Store** | `SQLAlchemy` with `sqlite3` | SQLite required; SQLAlchemy provides powerful ORM; cleaner code; SQL injection protection |
| **Agentic Layer & LLM** | `llama-index` with `Ollama` | Purpose-built for RAG pipelines; Ollama simplifies local LLM management |

### LLM Recommendation
- **Model:** 4-bit quantized ~7B parameter model (Mistral or Llama-3-8B-Instruct-Q4_K_M)
- **Rationale:** Runs effectively within 16GB RAM constraint

---

## 2. Data Flow Architecture

```
External Directory
       |
[1. File Watcher] --(new file path)--> [2. Ingestion Queue]
                                             | (pop file path)
                                             |
+-------------------- [3. Document Processor] ---------------------+
|                                                                  |
|  a. Read file & check hash against Metadata Store                |
|  b. Use 'unstructured' to parse & extract text/chunks (OCR)      |
|  c. Generate embeddings for chunks via 'sentence-transformers'   |
|  d. Save metadata/text to 'SQLite' & embeddings to 'ChromaDB'    |
|                                                                  |
+------------------------------------------------------------------+
       |                  |
[4. Metadata Store] [5. Vector DB]
     (SQLite)         (ChromaDB)
       ^                  ^
       |                  |
+------|------------------|-----------------+
|      |                  |                 |
| [6. Agentic Layer / API (LlamaIndex)] <---+---- [7. User Query]
|                                          |
|  a. Receive query via API                |
|  b. Generate embedding for query         |
|  c. Query Vector DB for similar chunks   |
|  d. Retrieve context from Metadata Store |
|  e. Synthesize answer with LLM (Ollama)  |
|  f. Return answer and sources            |
|                                          |
+------------------------------------------+
```

---

## 3. Database Schema (SQLite)

### `documents` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `file_path` | TEXT NOT NULL UNIQUE | Absolute path to source file |
| `file_hash` | TEXT NOT NULL | SHA256 hash for deduplication |
| `document_type` | TEXT | Mime type or file extension |
| `status` | TEXT NOT NULL | 'pending', 'processing', 'completed', 'error' |
| `created_at` | TIMESTAMP | When document was first seen |
| `processed_at` | TIMESTAMP | Last successful processing time |
| `error_message` | TEXT | Any error encountered |

### `document_chunks` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique identifier |
| `document_id` | INTEGER FK | Links to source document |
| `vector_id` | TEXT NOT NULL UNIQUE | UUID for ChromaDB lookup |
| `chunk_text` | TEXT | Raw text content |
| `metadata_json` | TEXT | JSON blob (page number, section, etc.) |

---

## 4. API Surface

### Internal Component Interfaces

**IngestionService → DocumentProcessor**
- `process_document(file_path: str)`: Initiates ingestion pipeline

**DocumentProcessor → VectorDB**
- `upsert_chunks(chunks: List[ChunkData])`: Batch insert/update chunks

**DocumentProcessor → MetadataStore**
- `get_document_by_hash(file_hash: str) -> Optional[Document]`
- `create_document_and_chunks(doc_data, chunk_data)`
- `update_document_status(doc_id: int, status: str, error: str = None)`

**AgenticLayer → VectorDB**
- `query_similar_chunks(query_embedding: List[float], top_k: int) -> List[QueryResult]`

**AgenticLayer → MetadataStore**
- `get_chunks_by_vector_ids(ids: List[str]) -> List[DocumentChunk]`
- `get_document_info(doc_id: int) -> Document`

### User-Facing REST API (FastAPI)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/query` | POST | Query the archive |
| `/api/documents` | GET | List all documents |
| `/api/documents/{id}/status` | GET | Get document processing status |

**Query Example:**
```json
// POST /api/query
{"query": "What is project X about?"}

// Response
{
  "answer": "...",
  "sources": [{"file_path": "/path/to/doc.pdf", "page": 4}]
}
```

---

## 5. Key Design Decisions

### 5.1 Asynchronous, Queue-based Ingestion
- **Decision:** File watcher places paths into queue; separate worker consumes
- **Rationale:** Decouples discovery from CPU-intensive processing; prevents overwhelm; crash-resilient

### 5.2 `unstructured` as Universal Parser
- **Decision:** Use `unstructured` for all document types instead of separate code
- **Rationale:** Drastically simplifies development; consistent pipeline; handles messy documents

### 5.3 Local-First, Quantized Models
- **Decision:** `all-MiniLM-L6-v2` + quantized LLM via Ollama
- **Rationale:** Meets privacy and hardware constraints; runs in 16GB RAM

### 5.4 Decoupled Metadata and Vector Stores
- **Decision:** SQLite for structured metadata, Chroma for vectors
- **Rationale:** SQLite fast/reliable for relational data; Chroma optimized for vector search; scales independently

---

## 6. Potential Bottlenecks & Mitigation

### 6.1 OCR and Embedding CPU Usage
**Problem:** Most computationally expensive; slow on NAS/mini-PC CPU

**Mitigation:**
- **Batching:** Process in batches for CPU cache efficiency
- **Background Processing:** Heavy lifting doesn't block queries
- **User Communication:** UI indicates processing time for large archives

### 6.2 RAM Consumption
**Problem:** LLM is largest RAM consumer

**Mitigation:**
- **Quantization:** 4-bit models (Q4_K_M) reduce RAM by 70%+
- **On-Demand Loading:** Load LLM when query arrives; unload after timeout
- **Swap File:** Adequate swap prevents crashes at cost of performance

### 6.3 Initial Backfill of 50,000 Documents
**Problem:** First run extremely long

**Mitigation:**
- **Dedicated Script:** Separate "backfill" script with aggressive batching
- **Prioritization:** Prioritize newer files in "watch" mode; recent docs searchable quickly
