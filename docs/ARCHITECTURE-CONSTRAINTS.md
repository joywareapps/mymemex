# Architecture Constraints & Design Principles

**Date:** 2026-02-15
**Status:** Authoritative — takes precedence over conflicting recommendations in other proposals

---

## 1. LLM/AI Externalization (Critical)

### 1.1 No In-Process AI Dependencies

**Constraint:** The application MUST NOT include PyTorch, TensorFlow, or any ML framework as a direct dependency.

**Rationale:**
- **Deployment flexibility:** Users can run the heavy AI workloads on different hardware than the NAS
- **Resource isolation:** NAS CPU/RAM is limited; AI shouldn't compete with core functionality
- **Model flexibility:** Users can choose any LLM provider (local Ollama, OpenAI, Anthropic, etc.)
- **Install size:** Keeps the application lightweight and fast to install

**Implications:**
- ❌ NO `sentence-transformers` (pulls in PyTorch)
- ❌ NO `transformers` library
- ❌ NO local model loading
- ✅ YES to HTTP-based AI APIs (Ollama, OpenAI, Anthropic, etc.)
- ✅ YES to `litellm` as unified interface

### 1.2 Ollama as Primary AI Backend

**Default configuration:** Ollama running on user's most capable machine (gaming PC, GPU server, etc.)

**Supported workflows:**
```
Scenario A: GPU Server on Same Network
┌─────────────┐         ┌──────────────────┐
│   NAS       │  HTTP   │  Gaming PC       │
│  MyMemex  │◄───────►│  Ollama Server   │
│  (low RAM)  │         │  (RTX 4090)      │
└─────────────┘         └──────────────────┘

Scenario B: Cloud Provider
┌─────────────┐         ┌──────────────────┐
│   NAS       │  HTTPS  │  OpenAI/Anthropic│
│  MyMemex  │◄───────►│  API             │
└─────────────┘         └──────────────────┘

Scenario C: Local Ollama on NAS (if powerful enough)
┌─────────────┐
│   NAS       │
│  MyMemex  │
│  + Ollama   │
└─────────────┘
```

### 1.3 Provider Agnosticism

**Constraint:** All LLM calls must go through an abstraction layer that supports:
- Local Ollama
- OpenAI API
- Anthropic API
- Any OpenAI-compatible endpoint (vLLM, LocalAI, etc.)

**Implementation:** `litellm` as the unified interface

**Configuration example:**
```yaml
llm:
  provider: ollama  # or openai, anthropic, custom
  base_url: http://192.168.1.100:11434  # Ollama on gaming PC
  model: llama3.2:latest
  embedding_model: nomic-embed-text:latest
  
  # Alternative configurations (user can switch)
  # provider: openai
  # api_key: ${OPENAI_API_KEY}
  # model: gpt-4o-mini
```

---

## 2. Graceful Degradation

### 2.1 AI-Dependent Features Must Degrade

**Constraint:** When the LLM backend is unavailable, the application must remain functional for non-AI operations.

| Feature | LLM Available | LLM Unavailable |
|---------|--------------|-----------------|
| Document ingestion | ✅ Full pipeline | ⏳ Queued (waits for LLM) |
| OCR processing | ✅ Full | ✅ Still works (CPU-based) |
| Text extraction (PyMuPDF) | ✅ Full | ✅ Still works |
| Vector embeddings | ⏳ Queued | ⏳ Queued |
| Auto-tagging | ⏳ Queued | ⏳ Skipped, manual tags only |
| Classification | ⏳ Queued | ⏳ Skipped |
| Filing suggestions | ⏳ Queued | ⏳ Skipped |
| Keyword search (FTS5) | ✅ Full | ✅ Still works |
| Semantic search | ❌ Blocked | ❌ Blocked (no embeddings) |
| RAG Q&A | ❌ Blocked | ❌ Blocked |
| Document listing | ✅ Full | ✅ Still works |
| Tag management | ✅ Full | ✅ Still works |
| Document preview | ✅ Full | ✅ Still works |

### 2.2 Queue-Based Processing with Persistence

**Constraint:** All AI-dependent tasks must be:
1. **Persisted to disk** (survive restarts)
2. **Retryable** (exponential backoff)
3. **Interruptible** (can pause/resume)
4. **Prioritized** (user uploads > watcher > backfill)

**Queue states:**
```python
class TaskStatus(Enum):
    PENDING = "pending"           # Waiting to be processed
    WAITING_LLM = "waiting_llm"   # LLM unavailable, will retry
    PROCESSING = "processing"     # Currently being processed
    COMPLETED = "completed"       # Successfully processed
    FAILED = "failed"             # Permanent failure after max retries
    CANCELLED = "cancelled"       # User cancelled
```

### 2.3 Offline-First Document Access

**Constraint:** Once a document is processed, its core data must be accessible without the LLM:
- Extracted text (from OCR/PyMuPDF)
- Document metadata (title, date, file path)
- User-applied tags (manual tagging always works)
- Keyword search (FTS5)
- Document preview/thumbnails

**What requires LLM:**
- Vector embeddings (for semantic search)
- Auto-generated tags
- Document classification
- RAG Q&A

---

## 3. Hybrid Online/Offline Architecture

### 3.1 Core Principle

**"Index locally, query anywhere"**

- **Indexing phase:** Requires LLM for embeddings, tagging, classification — run when powerful hardware is available
- **Query phase:** Semantic search and RAG require LLM connection — but keyword search and document browsing work offline

### 3.2 Reconnection Behavior

When LLM becomes available after being offline:
1. **Auto-resume queued tasks** — process pending embeddings, tags, classifications
2. **Re-index detection** — optionally re-embed documents if embedding model changed
3. **Backfill completion** — finish any interrupted bulk processing

```python
class LLMConnectionManager:
    """Manages LLM availability and task resumption."""
    
    async def on_llm_available(self):
        """Called when LLM connection is restored."""
        # 1. Resume pending embedding tasks
        await self.queue.resume_tasks(status=TaskStatus.WAITING_LLM)
        
        # 2. Process any new documents that arrived while offline
        await self.watcher.process_backlog()
        
        # 3. Notify UI via WebSocket
        await self.ws.broadcast({"event": "llm.available"})
    
    async def on_llm_unavailable(self):
        """Called when LLM connection is lost."""
        # 1. Pause AI-dependent tasks
        await self.queue.pause_tasks(requires_llm=True)
        
        # 2. Update task statuses
        await self.queue.set_status(
            status=TaskStatus.PROCESSING,
            new_status=TaskStatus.WAITING_LLM
        )
        
        # 3. Notify UI
        await self.ws.broadcast({"event": "llm.unavailable"})
```

---

## 4. Connection String Configuration

### 4.1 Flexible Endpoint Configuration

All AI-related endpoints must be configurable:

```yaml
# config.yaml

# Primary LLM for generation
llm:
  provider: ollama
  base_url: http://192.168.1.100:11434
  model: llama3.2:latest
  timeout: 120
  max_retries: 3

# Embedding model (can be same or different endpoint)
embedding:
  provider: ollama  # Can differ from LLM provider
  base_url: http://192.168.1.100:11434
  model: nomic-embed-text:latest
  batch_size: 32

# Cloud OCR fallback (optional)
ocr:
  primary: local  # paddleocr
  fallback: 
    provider: aws
    region: us-east-1
    # or google_vision, azure_form_recognizer
```

### 4.2 Environment Variable Support

All connection strings should support environment variable interpolation:

```yaml
llm:
  base_url: ${OLLAMA_HOST:http://localhost:11434}
  api_key: ${OPENAI_API_KEY:}  # Empty default for local
```

---

## 5. Implications for Library Choices

### 5.1 Required Libraries

| Library | Purpose | Reason |
|---------|---------|--------|
| `litellm` | LLM abstraction | Unified interface, handles fallbacks |
| `httpx` | HTTP client | Async, connection pooling |
| `ollama` (optional) | Ollama-specific client | Convenience wrapper |

### 5.2 Forbidden Libraries

| Library | Why Forbidden | Alternative |
|---------|---------------|-------------|
| `sentence-transformers` | PyTorch dependency | Ollama embeddings API |
| `transformers` | PyTorch dependency | LiteLLM + external provider |
| `torch` | Heavy, GPU-dependent | N/A (externalize) |
| `tensorflow` | Heavy | N/A |

### 5.3 Embedding Strategy

**Option A: Ollama Embeddings (Recommended)**
```python
# Call Ollama's embedding endpoint
response = await httpx.post(
    f"{OLLAMA_BASE_URL}/api/embeddings",
    json={"model": "nomic-embed-text", "prompt": text}
)
embedding = response.json()["embedding"]
```

**Option B: OpenAI Embeddings**
```python
# Via LiteLLM
response = await litellm.aembedding(
    model="text-embedding-3-small",
    input=[text],
    api_base=OPENAI_BASE_URL
)
```

**Option C: Any OpenAI-Compatible Endpoint**
```python
# vLLM, LocalAI, etc.
response = await litellm.aembedding(
    model="local-model",
    input=[text],
    api_base="http://gpu-server:8000/v1"
)
```

---

## 6. User Experience Considerations

### 6.1 Status Indicators

UI must clearly show:
- ✅ LLM connected (which provider, which model)
- ⏳ LLM unavailable (X tasks queued)
- 🔄 Processing (Y documents in queue, Z% complete)
- ⚠️ Degraded mode (semantic search unavailable, keyword search only)

### 6.2 Settings UI

Users should be able to:
- Change LLM provider without restart
- Configure multiple provider profiles (home GPU, cloud fallback)
- Test connection before saving
- View connection status and latency

---

## 7. Summary: Architectural Principles

1. **Externalize all AI** — No ML frameworks in the application process
2. **Network-transparent AI** — LLM can run anywhere reachable via HTTP
3. **Graceful degradation** — Core functionality works without LLM
4. **Queue persistence** — Tasks survive restarts and LLM outages
5. **Provider agnostic** — Easy switching between Ollama, OpenAI, Anthropic, etc.
6. **Offline-first document access** — Browsing and keyword search always work
7. **Clear user feedback** — Always show AI availability status
